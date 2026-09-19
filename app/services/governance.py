import re
from datetime import datetime
from pathlib import Path
from pypdf import PdfReader
from flask import current_app

from app.extensions import db
from app.models import GovernanceDocument, GovernanceMember, Teacher, TeacherHistory
from app.services.suap import api_get_custom


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

def _server_summary(matricula):
    """Consulta o endpoint documentado /api/rh/servidor-resumido/.

    O schema documentado no SUAP retorna matrícula, nome, campus, e-mail e foto.
    Alguns usuários podem receber 403 nesse endpoint; nesse caso retornamos None
    para que a importação da portaria continue sem interromper o processo.
    """
    try:
        data = api_get_custom(
            'rh/servidor-resumido/',
            {'matricula': str(matricula)},
        )
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _server_photo_map(identifiers=None):
    """Obtém fotos por matrícula usando o endpoint oficial documentado.

    Primeiro tenta /rh/servidor-resumido/?matricula=..., que documenta
    explicitamente o campo `foto`. Se nenhum identificador for informado,
    percorre /rh/servidores/ como fallback.
    """
    photos = {}
    ids = [str(x) for x in (identifiers or []) if x not in (None, '')]

    if ids:
        for ident in ids:
            data = _server_summary(ident)
            if not data:
                continue
            photo = data.get('foto') or data.get('foto_url') or data.get('url_foto')
            if photo:
                photo = str(photo)
                if not photo.startswith(('http://', 'https://', 'data:')):
                    photo = current_app.config['SUAP_BASE_URL'].rstrip('/') + '/' + photo.lstrip('/')
                photos[ident] = photo
        return photos

    # Fallback para a coleção de servidores, caso ela esteja autorizada.
    offset = 0
    limit = 100
    while True:
        try:
            data = api_get_custom(current_app.config['SUAP_ENDPOINT_SERVERS'], {'limit': limit, 'offset': offset})
        except Exception:
            break
        results = data.get('results', data if isinstance(data, list) else [])
        if not results:
            break
        for item in results:
            photo = next((item.get(k) for k in ('foto', 'foto_url', 'url_foto', 'imagem', 'image', 'url_imagem', 'foto_servidor') if item.get(k)), None)
            if not photo:
                continue
            photo = str(photo)
            if not photo.startswith(('http://', 'https://', 'data:')):
                photo = current_app.config['SUAP_BASE_URL'].rstrip('/') + '/' + photo.lstrip('/')
            for ident in (item.get('matricula'), item.get('siape'), item.get('id'), item.get('identificacao')):
                if ident not in (None, ''):
                    photos[str(ident)] = photo
        offset += len(results)
        count = data.get('count') if isinstance(data, dict) else None
        if count is not None and offset >= int(count):
            break
        if len(results) < limit or offset > 100000:
            break
    return photos


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
                photo = server_data.get('foto') or server_data.get('foto_url') or server_data.get('url_foto')
                if photo:
                    photo = str(photo)
                    if not photo.startswith(('http://', 'https://', 'data:')):
                        photo = current_app.config['SUAP_BASE_URL'].rstrip('/') + '/' + photo.lstrip('/')
                    teacher.photo_url = photo

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

