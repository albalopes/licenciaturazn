from datetime import datetime
from urllib.parse import urlparse, parse_qs

from app.extensions import db
from app.models import Project
from app.services.suap import api_get_custom, api_get_url
from flask import current_app

CAMPUS_ALIASES = (
    'natal-zona-norte', 'natal zona norte', 'natal zona norte - zn',
    'natal zona norte (zn)', 'campus natal zona norte', 'natal - zona norte',
    'natal-zona norte', 'zona norte', 'zn',
)

# Endpoints confirmados no /api/openapi.json fornecido pelo SUAP em 18/09/2026.
# A documentação atual não apresenta endpoint de Projetos de Ensino.
ENDPOINTS = {
    'pesquisa': 'pesquisa/projetos/',
    'extensao': 'extensao/projetos/',
}


def _text(item, *keys):
    for key in keys:
        value = item.get(key)
        if value in (None, ''):
            continue
        if isinstance(value, dict):
            nested = next((value.get(k) for k in ('nome', 'name', 'descricao', 'description', 'label', 'value', 'sigla', 'codigo') if value.get(k) not in (None, '')), None)
            if nested is not None:
                return nested
        if isinstance(value, (list, tuple)):
            return ', '.join(str(v.get('nome') or v.get('name') or v) if isinstance(v, dict) else str(v) for v in value)
        return value
    return ''


def _campus_match(value):
    s = ' '.join(str(value or '').lower().replace('_', ' ').replace('-', ' ').split())
    configured = ' '.join(str(current_app.config.get('SUAP_PROJECT_CAMPUS', 'Natal-Zona-Norte')).lower().replace('-', ' ').split())
    if configured and (configured in s or s in configured):
        return True
    aliases = [' '.join(a.replace('-', ' ').split()) for a in CAMPUS_ALIASES]
    return any(a == s or a in s or s in a for a in aliases)


def _normalize_status(value):
    if isinstance(value, dict):
        return str(_text(value, 'descricao', 'nome', 'label', 'value') or '').strip()
    return str(value or '').strip()


def _is_active(item):
    for key in ('ativo', 'active', 'em_execucao', 'em_andamento'):
        if key in item and item[key] is not None:
            return bool(item[key])
    status = _normalize_status(_text(item, 'situacao', 'status', 'situacao_projeto', 'estado', 'status_projeto')).lower()
    if any(x in status for x in ('cancel', 'finaliz', 'conclu', 'arquiv', 'inativ', 'encerr')):
        return False
    end = _text(item, 'data_fim', 'fim', 'data_final', 'end_date', 'data_termino', 'dt_final')
    if end:
        try:
            from dateutil import parser
            return parser.parse(str(end)).date() >= datetime.utcnow().date()
        except Exception:
            pass
    return True


def _normalize(item, ptype):
    campus = _text(item, 'campus_nome', 'campus_nome_formatado', 'campus', 'campus_sigla', 'unidade', 'unidade_nome', 'campi', 'campus_descricao')
    title = _text(item, 'titulo', 'title', 'nome', 'projeto', 'nome_projeto')
    desc = _text(item, 'resumo', 'descricao', 'description', 'objetivo_geral', 'apresentacao') or title
    coordinator = _text(item, 'nome_coordenador', 'coordenador', 'coordenador_nome', 'responsavel', 'responsavel_nome', 'servidor_responsavel')
    period = _text(item, 'periodo', 'period', 'vigencia')
    if not period:
        start = _text(item, 'dt_inicio', 'data_inicio', 'inicio', 'start_date')
        end = _text(item, 'data_fim', 'fim', 'data_final', 'end_date', 'data_termino', 'dt_final')
        period = f'{start} – {end}' if start and end else (start or end)
    status = _normalize_status(_text(item, 'situacao', 'status', 'estado', 'status_projeto')) or ('Em andamento' if _is_active(item) else 'Concluído')
    external_id = _text(item, 'id', 'pk', 'codigo', 'numero', 'projeto_id')
    url = _text(item, 'url', 'link', 'detail_url', 'url_projeto')
    team = _text(item, 'equipe', 'participantes', 'alunos', 'membros')
    acronym = _text(item, 'sigla', 'acronimo', 'acronym')
    academic_year = _text(item, 'ano', 'ano_execucao', 'ano_projeto')
    if not academic_year:
        start = _text(item, 'dt_inicio', 'data_inicio', 'inicio')
        if start:
            try:
                academic_year = str(start)[:4]
            except Exception:
                pass
    funding = _text(item, 'fomento', 'financiamento', 'edital', 'programa')
    partners = _text(item, 'parceiros', 'instituicoes_parceiras')
    objectives = _text(item, 'objetivos', 'objetivo_geral')
    return dict(
        suap_id=str(external_id) if external_id else None,
        title=str(title), acronym=str(acronym) if acronym else None,
        project_type=ptype, description=str(desc), objectives=str(objectives) if objectives else None,
        coordinator=str(coordinator) if coordinator else None, period=str(period) if period else None,
        status=str(status), campus=str(campus) if campus else None, team=str(team) if team else None,
        academic_year=int(academic_year) if str(academic_year).isdigit() else None,
        funding=str(funding) if funding else None, partners=str(partners) if partners else None,
        url=str(url) if url else None,
    )


def _fetch_pages(endpoint, max_pages=5):
    """Busca somente um número controlado de páginas da API.

    A documentação atual do SUAP expõe apenas o parâmetro `page` para os
    endpoints de projetos; campus e período são filtrados localmente.
    Isso evita que uma sincronização administrativa percorra toda a base.
    """
    results_all = []
    seen_ids = set()
    next_url = None
    page = 1
    max_pages = max(1, min(int(max_pages or 5), 100))
    for _ in range(max_pages):
        data = api_get_url(next_url) if next_url else api_get_custom(endpoint, {'page': page})
        results = data if isinstance(data, list) else data.get('results', [])
        if not results:
            break
        for item in results:
            ident = _text(item, 'id', 'pk', 'codigo', 'numero', 'projeto_id')
            key = str(ident) if ident not in (None, '') else repr(item)
            if key not in seen_ids:
                seen_ids.add(key)
                results_all.append(item)
        if not isinstance(data, dict):
            break
        next_url = data.get('next')
        if not next_url:
            count = data.get('count')
            if count is None or len(results_all) >= int(count):
                break
            page += 1
            continue
        # The `next` URL already contains the next page.
    return results_all, next_url


def sync_projects(project_types=None, start_year=None, end_year=None, max_pages=5, campus="Natal-Zona-Norte"):
    current_app.config["SUAP_PROJECT_CAMPUS"] = campus or current_app.config.get("SUAP_PROJECT_CAMPUS", "Natal-Zona-Norte")
    imported = []
    errors = []
    project_types = [p for p in (project_types or list(ENDPOINTS)) if p in ENDPOINTS]
    stats = {p: {'fetched': 0, 'matched': 0, 'pending': 0, 'updated': 0} for p in project_types}
    for ptype in project_types:
        endpoint = ENDPOINTS[ptype]
        try:
            results, _next_url = _fetch_pages(endpoint, max_pages=max_pages)
        except Exception as exc:
            errors.append(f'{ptype}: {exc}')
            continue
        stats[ptype]['fetched'] = len(results)
        for raw in results:
            item = _normalize(raw, ptype)
            if not item['title'] or not _campus_match(item['campus']):
                continue
            if start_year is not None or end_year is not None:
                year = item.get('academic_year')
                if year is None:
                    continue
                if start_year is not None and year < start_year:
                    continue
                if end_year is not None and year > end_year:
                    continue
            stats[ptype]['matched'] += 1
            project = None
            if item['suap_id']:
                project = Project.query.filter_by(suap_id=item['suap_id'], project_type=ptype).first()
            if not project:
                project = Project.query.filter_by(title=item['title'], project_type=ptype, campus=item['campus']).first()
            if not project:
                # Staging: nothing becomes public before the administrator accepts it.
                project = Project(source_system='suap', import_status='pending', published=False, **item)
                db.session.add(project)
                stats[ptype]['pending'] += 1
            else:
                was_pending = project.import_status == 'pending'
                for key, value in item.items():
                    setattr(project, key, value)
                project.source_system = 'suap'
                # Accepted/rejected decisions are preserved across later synchronizations.
                if was_pending:
                    project.published = False
                    stats[ptype]['pending'] += 1
                else:
                    stats[ptype]['updated'] += 1
            imported.append(project)
    db.session.commit()
    return imported, errors, stats
