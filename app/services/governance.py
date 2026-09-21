import re
from datetime import datetime
from pathlib import Path
from pypdf import PdfReader
from flask import current_app

from app.extensions import db
from app.models import GovernanceDocument, GovernanceMember, Teacher, TeacherHistory
from app.services.suap import api_get_custom, api_get_url


def _clean(value):
    return re.sub(r'\s+', ' ', (value or '')).strip()


def _parse_portaria_header(text):
    m = re.search(r'PORTARIA Nº\s*([^\n]+?)\s*\n\s*(\d{1,2} de [^\n]+ de \d{4})', text, re.I)
    if not m:
        m = re.search(r'PORTARIA Nº\s*([^\n]+)', text, re.I)
    number = _clean(m.group(1)) if m else ''
    date = None
    if m and len(m.groups()) > 1:
        try:
            months = {'janeiro':1,'fevereiro':2,'março':3,'abril':4,'maio':5,'junho':6,'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
            d = re.search(r'(\d{1,2}) de ([a-zç]+) de (\d{4})', m.group(2), re.I)
            if d:
                date = datetime(int(d.group(3)), months[d.group(2).lower()], int(d.group(1))).date()
        except Exception:
            pass
    return number, date


def _semester_from_text(text):
    m = re.search(r'per[ií]odo letivo de (\d{4}\.\d)', text, re.I)
    return m.group(1) if m else None


def parse_governance_pdf(path: str | Path, body: str):
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(str(path)).pages)
    number, issued_at = _parse_portaria_header(text)
    semester = _semester_from_text(text)
    if not semester and issued_at:
        semester = f'{issued_at.year}.{2 if issued_at.month >= 7 else 1}'

    lines = [_clean(x) for x in text.splitlines() if _clean(x)]
    functions = ('Coordenadora', 'Coordenador', 'Docente', 'Discente', 'Equipe Técnico-Pedagógica')
    members = []
    atuacao_semesters = []

    def is_mat(value):
        return bool(re.fullmatch(r'\d{5,20}', value.replace('.', '').strip()))

    def skip_noise(value):
        return value.lower() in ('matrícula', 'nome', 'função', 'atuação', 'x') or bool(re.fullmatch(r'\d{4}\.\d', value))

    # Algumas portarias, como a do Colegiado 2026.1, trazem uma coluna
    # ATUAÇÃO com vários semestres. Capturamos os rótulos para preservar esse
    # histórico, em vez de considerar apenas o semestre da portaria.
    for idx, line in enumerate(lines):
        if 'atuação' in line.lower():
            found = []
            for candidate in lines[idx + 1:idx + 4]:
                for value in re.findall(r'\b\d{4}\.\d\b', candidate):
                    if value not in found:
                        found.append(value)
            if found:
                atuacao_semesters = found
                break

    def split_role_marks(value):
        marks = len(re.findall(r'(?<!\d)x(?!\d)', value.lower()))
        role = re.sub(r'\s+x(?:\s+x)*\s*$', '', value, flags=re.I).strip()
        return role, marks

    def append_member(siape, name, role, marks=0):
        role, trailing_marks = split_role_marks(role)
        marks += trailing_marks
        substitute = 'suplente' in role.lower() or 'suplente' in name.lower()
        role = re.sub(r'\s*\(.*?suplente.*?\)', '', role, flags=re.I).strip()
        name = re.sub(r'\s*\(.*?suplente.*?\)', '', name, flags=re.I).strip()
        if not name:
            return
        item = {'siape': siape, 'name': name, 'role': role, 'substitute': substitute, 'atuacao': []}
        if atuacao_semesters and marks:
            item['atuacao'] = atuacao_semesters[:marks]
        members.append(item)

    i = 0
    while i < len(lines):
        if skip_noise(lines[i]):
            i += 1
            continue
        if is_mat(lines[i]):
            siape = lines[i].replace('.', '')
            i += 1
            name_parts = []
            while i < len(lines) and not is_mat(lines[i]) and not any(lines[i].lower().startswith(f.lower()) for f in functions):
                if skip_noise(lines[i]):
                    i += 1
                    continue
                if lines[i].upper() in ('CÓDIGO VERIFICADOR:', 'CÓDIGO DE AUTENTICAÇÃO:'):
                    break
                name_parts.append(lines[i])
                i += 1
            if i < len(lines) and any(lines[i].lower().startswith(f.lower()) for f in functions):
                role = lines[i]
                i += 1
                marks = 0
                role, marks = split_role_marks(role)
                while i < len(lines) and re.fullmatch(r'x(?:\s+x)*', lines[i], flags=re.I):
                    marks += len(re.findall(r'\bx\b', lines[i], flags=re.I))
                    i += 1
                if i < len(lines) and 'suplente' in lines[i].lower():
                    substitute = True
                    i += 1
                else:
                    substitute = 'suplente' in role.lower()
                role = re.sub(r'\s*\(.*?suplente.*?\)', '', role, flags=re.I).strip()
                name = _clean(' '.join(name_parts))
                if name:
                    item = {'siape': siape, 'name': name, 'role': role, 'substitute': substitute, 'atuacao': atuacao_semesters[:marks] if atuacao_semesters and marks else []}
                    members.append(item)
            continue

        # name-first: collect name fragments until matrícula, then role.
        name_parts = [lines[i]]
        i += 1
        while i < len(lines) and not is_mat(lines[i]):
            if any(lines[i].lower().startswith(f.lower()) for f in functions) or skip_noise(lines[i]):
                break
            name_parts.append(lines[i])
            i += 1
        if i < len(lines) and is_mat(lines[i]):
            siape = lines[i].replace('.', '')
            i += 1
            if i < len(lines) and any(lines[i].lower().startswith(f.lower()) for f in functions):
                role = lines[i]
                i += 1
                role, marks = split_role_marks(role)
                while i < len(lines) and re.fullmatch(r'x(?:\s+x)*', lines[i], flags=re.I):
                    marks += len(re.findall(r'\bx\b', lines[i], flags=re.I))
                    i += 1
                substitute = 'suplente' in role.lower()
                if i < len(lines) and 'suplente' in lines[i].lower():
                    substitute = True
                    i += 1
                role = re.sub(r'\s*\(.*?suplente.*?\)', '', role, flags=re.I).strip()
                name = _clean(' '.join(name_parts))
                if name:
                    members.append({'siape': siape, 'name': name, 'role': role, 'substitute': substitute, 'atuacao': atuacao_semesters[:marks] if atuacao_semesters and marks else []})
    return {'number': number, 'issued_at': issued_at, 'semester': semester, 'members': members, 'text': text}

def _server_results(campus='ZN', matricula=None):
    """Consulta /api/rh/servidores/ usando campus, matrícula e page."""
    results = []
    seen = set()
    next_url = None
    page = 1
    for _ in range(1000):
        if next_url:
            data = api_get_url(next_url)
        else:
            params = {'campus': campus, 'page': page}
            if matricula:
                params['matricula'] = str(matricula)
            data = api_get_custom(current_app.config['SUAP_ENDPOINT_SERVERS'], params)
        page_results = data if isinstance(data, list) else data.get('results', [])
        if not page_results:
            break
        for item in page_results:
            ident = item.get('matricula') or item.get('siape') or item.get('id')
            key = str(ident) if ident not in (None, '') else repr(item)
            if key not in seen:
                seen.add(key)
                results.append(item)
        if not isinstance(data, dict):
            break
        next_url = data.get('next')
        if next_url:
            continue
        count = data.get('count')
        if count is not None and len(results) < int(count):
            page += 1
            continue
        break
    return results

def _server_summary(matricula):
    """Obtém os dados de um servidor pela coleção /rh/servidores/.

    A documentação exibida pelo usuário mostra que este endpoint aceita
    campus=ZN e matricula, e retorna matrícula, nome, cargo, campus,
    url_foto_75x100 e outros dados funcionais. O endpoint resumido é usado
    apenas como fallback porque pode responder 403 para alguns tokens.
    """
    if not matricula:
        return None
    try:
        results = _server_results(campus=current_app.config.get('SUAP_CAMPUS_SIGLA', 'ZN'), matricula=str(matricula))
        target = str(matricula)
        for item in results:
            if str(item.get('matricula', '')).strip() == target:
                return item
        return results[0] if results else None
    except Exception:
        pass

    # Fallback: endpoint resumido documentado, quando o token tiver essa permissão.
    try:
        data = api_get_custom('rh/servidor-resumido/', {'matricula': str(matricula)})
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _photo_from_server(data):
    if not isinstance(data, dict):
        return None
    photo = next((data.get(k) for k in (
        'url_foto_75x100', 'url_foto', 'foto', 'foto_url', 'imagem', 'image',
        'url_imagem', 'foto_servidor'
    ) if data.get(k)), None)
    if not photo:
        return None
    photo = str(photo)
    if photo.startswith(('http://', 'https://', 'data:')):
        return photo
    return current_app.config['SUAP_BASE_URL'].rstrip('/') + '/' + photo.lstrip('/')


def _server_photo_map(identifiers=None):
    """Obtém fotos dos servidores usando /rh/servidores/?campus=ZN.

    Quando são informadas matrículas, a API é consultada diretamente por matrícula,
    evitando baixar todos os servidores. Sem matrículas, baixa a coleção paginada
    do Campus ZN e indexa por matrícula.
    """
    photos = {}
    ids = [str(x) for x in (identifiers or []) if x not in (None, '')]
    campus = current_app.config.get('SUAP_CAMPUS_SIGLA', 'ZN')

    if ids:
        for ident in ids:
            data = _server_summary(ident)
            photo = _photo_from_server(data)
            if photo:
                photos[ident] = photo
        return photos

    try:
        for item in _server_results(campus=campus):
            photo = _photo_from_server(item)
            if not photo:
                continue
            for ident in (item.get('matricula'), item.get('siape'), item.get('id'), item.get('identificacao')):
                if ident not in (None, ''):
                    photos[str(ident)] = photo
    except Exception:
        pass
    return photos


def sync_teacher_data_from_suap(teachers):
    """Atualiza dados funcionais/foto dos docentes já cadastrados no curso.

    Usa uma única varredura paginada do Campus ZN e cruza por matrícula/SIAPE.
    Não cria professores novos: a lista de docentes do curso continua sendo
    determinada pelas portarias do Colegiado/NDE.
    """
    by_id = {}
    for item in _server_results(campus=current_app.config.get('SUAP_CAMPUS_SIGLA', 'ZN')):
        for ident in (item.get('matricula'), item.get('siape'), item.get('id')):
            if ident not in (None, ''):
                by_id[str(ident)] = item

    updated = 0
    found = 0
    for teacher in teachers:
        ids = {str(x) for x in (getattr(teacher, 'siape', None), getattr(teacher, 'suap_id', None)) if x not in (None, '')}
        ids.update(str(m.siape) for m in GovernanceMember.query.filter_by(name=teacher.name).all() if m.siape)
        data = next((by_id[i] for i in ids if i in by_id), None)
        if not data:
            continue
        found += 1
        teacher.siape = str(data.get('matricula') or teacher.siape) if (data.get('matricula') or teacher.siape) else teacher.siape
        teacher.suap_id = teacher.suap_id or teacher.siape
        teacher.email = data.get('email') or teacher.email
        photo = _photo_from_server(data)
        if photo:
            teacher.photo_url = photo
        # Campos expostos pela coleção atual do SUAP /api/rh/servidores/.
        # Mantemos o valor manual quando a API não retornar o campo.
        lattes = data.get('curriculo_lattes') or data.get('lattes_url')
        if lattes:
            teacher.lattes_url = str(lattes)
        ingresso = data.get('disciplina_ingresso')
        if ingresso:
            teacher.ingresso_disciplina = str(ingresso)
        areas = data.get('cargo') or data.get('funcao')
        if areas and not teacher.areas:
            teacher.areas = str(areas)
        updated += 1
    db.session.commit()
    return found, updated

def import_governance(path, body, title=None, document_url=None):
    parsed = parse_governance_pdf(path, body)
    doc = GovernanceDocument(
        body=body, title=title or f'Portaria {parsed["number"]}', portaria_number=parsed['number'] or 'Não informado',
        issued_at=parsed['issued_at'], semester=parsed['semester'], document_url=document_url,
        file_path=str(path), active=True,
    )
    GovernanceDocument.query.filter_by(body=body, active=True).update({'active': False})
    db.session.add(doc)
    db.session.flush()

    for item in parsed['members']:
        member = GovernanceMember(
            body=body, name=item['name'], role=item['role'], term=parsed['semester'],
            document_url=document_url, siape=item['siape'], substitute=item['substitute'], semester=parsed['semester'],
            governance_document_id=doc.id, active=True,
        )
        db.session.add(member)

        if body in ('colegiado', 'nde') and item['role'].lower() in ('docente', 'coordenadora', 'coordenador'):
            teacher = Teacher.query.filter_by(name=item['name']).first()
            if not teacher and item['siape']:
                teacher = Teacher.query.filter_by(suap_id=str(item['siape'])).first() if hasattr(Teacher, 'suap_id') else None
            if not teacher:
                teacher = Teacher(name=item['name'], active=True)
                db.session.add(teacher)
                db.session.flush()
            if item['siape']:
                if hasattr(teacher, 'siape'):
                    teacher.siape = item['siape']
                if hasattr(teacher, 'suap_id'):
                    teacher.suap_id = item['siape']
            server_data = _server_summary(item['siape']) if item['siape'] else None
            if server_data:
                teacher.email = server_data.get('email') or teacher.email
                photo = _photo_from_server(server_data)
                if photo:
                    teacher.photo_url = photo
                teacher.lattes_url = server_data.get('curriculo_lattes') or server_data.get('lattes_url') or teacher.lattes_url
                teacher.ingresso_disciplina = server_data.get('disciplina_ingresso') or teacher.ingresso_disciplina

            semesters = item.get('atuacao') or [parsed['semester']]
            for term in semesters:
                if not term:
                    continue
                history = TeacherHistory.query.filter_by(teacher_id=teacher.id, semester=term, body=body).first()
                if not history:
                    db.session.add(TeacherHistory(
                        teacher_id=teacher.id, semester=term, body=body,
                        role=item['role'], governance_document_id=doc.id,
                    ))
    db.session.commit()
    return doc, parsed

