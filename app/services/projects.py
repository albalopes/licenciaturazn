from datetime import datetime
from urllib.parse import urlparse, parse_qs

from app.extensions import db
from app.models import Project
from app.services.suap import api_get_custom, api_get_url
from flask import current_app

CAMPUS_ALIASES = (
    'natal-zona-norte', 'natal zona norte', 'natal zona norte - zn',
    'natal zona norte (zn)', 'zona norte', 'zn',
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
            nested = next((value.get(k) for k in ('nome', 'name', 'descricao', 'description', 'label', 'value') if value.get(k) not in (None, '')), None)
            if nested is not None:
                return nested
        if isinstance(value, (list, tuple)):
            return ', '.join(str(v.get('nome') or v.get('name') or v) if isinstance(v, dict) else str(v) for v in value)
        return value
    return ''


def _campus_match(value):
    s = ' '.join(str(value or '').lower().replace('_', ' ').replace('-', ' ').split())
    configured = ' '.join(str(current_app.config.get('SUAP_PROJECT_CAMPUS', 'Natal-Zona-Norte')).lower().replace('-', ' ').split())
    return bool(configured and configured in s) or any(' '.join(a.replace('-', ' ').split()) in s for a in CAMPUS_ALIASES)


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
    end = _text(item, 'data_fim', 'fim', 'data_final', 'end_date', 'data_termino')
    if end:
        try:
            from dateutil import parser
            return parser.parse(str(end)).date() >= datetime.utcnow().date()
        except Exception:
            pass
    return True


def _normalize(item, ptype):
    campus = _text(item, 'campus', 'campus_nome', 'unidade', 'unidade_nome', 'campi', 'campus_descricao')
    title = _text(item, 'titulo', 'title', 'nome', 'projeto', 'descricao', 'nome_projeto')
    desc = _text(item, 'descricao', 'description', 'resumo', 'objetivo_geral', 'apresentacao') or title
    coordinator = _text(item, 'coordenador', 'coordenador_nome', 'responsavel', 'responsavel_nome', 'servidor_responsavel')
    period = _text(item, 'periodo', 'period', 'vigencia')
    if not period:
        start = _text(item, 'data_inicio', 'inicio', 'start_date')
        end = _text(item, 'data_fim', 'fim', 'data_final', 'end_date', 'data_termino')
        period = f'{start} – {end}' if start and end else (start or end)
    status = _normalize_status(_text(item, 'situacao', 'status', 'estado', 'status_projeto')) or ('Em andamento' if _is_active(item) else 'Concluído')
    external_id = _text(item, 'id', 'pk', 'codigo', 'numero', 'projeto_id')
    url = _text(item, 'url', 'link', 'detail_url', 'url_projeto')
    team = _text(item, 'equipe', 'participantes', 'alunos', 'membros')
    acronym = _text(item, 'sigla', 'acronimo', 'acronym')
    academic_year = _text(item, 'ano', 'ano_execucao', 'ano_projeto')
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


def _fetch_all(endpoint, page_size=100):
    """Percorre a paginação da API atual documentada pelo SUAP."""
    results_all = []
    seen_ids = set()
    next_url = None
    page = 1
    for _ in range(1000):
        data = api_get_url(next_url) if next_url else api_get_custom(endpoint, {'page': page})
        results = data if isinstance(data, list) else data.get('results', [])
        if not results:
            break
        added = 0
        for item in results:
            ident = _text(item, 'id', 'pk', 'codigo', 'numero', 'projeto_id')
            key = str(ident) if ident not in (None, '') else repr(item)
            if key not in seen_ids:
                seen_ids.add(key)
                results_all.append(item)
                added += 1
        next_url = data.get('next') if isinstance(data, dict) else None
        if next_url:
            page += 1
            continue
        count = data.get('count') if isinstance(data, dict) else None
        if count is not None and len(results_all) >= int(count):
            break
        if len(results) < page_size or added == 0:
            break
        page += 1
    return results_all


def sync_projects():
    imported = []
    errors = []
    for ptype, endpoint in ENDPOINTS.items():
        try:
            results = _fetch_all(endpoint)
        except Exception as exc:
            errors.append(f'{ptype}: {exc}')
            continue
        for raw in results:
            if not _is_active(raw):
                continue
            item = _normalize(raw, ptype)
            if not _campus_match(item['campus']) or not item['title']:
                continue
            project = None
            if item['suap_id']:
                project = Project.query.filter_by(suap_id=item['suap_id'], project_type=ptype).first()
            if not project:
                project = Project.query.filter_by(title=item['title'], project_type=ptype, campus=item['campus']).first()
            if not project:
                project = Project(source_system='suap', **item)
                db.session.add(project)
            else:
                # Nunca sobrescrever as anotações feitas pela Coordenação.
                for key, value in item.items():
                    setattr(project, key, value)
                project.source_system = 'suap'
            project.published = True
            imported.append(project)
    db.session.commit()
    return imported, errors
