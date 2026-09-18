from datetime import datetime

from app.extensions import db
from app.models import Project
from app.services.suap import SuapOAuthError, api_get_custom
from flask import current_app

CAMPUS_ALIASES = (
    'natal-zona-norte',
    'natal zona norte',
    'natal zona norte - zn',
    'natal zona norte (zn)',
    'zona norte',
    'zn',
)

# Rotas da API /api/ atualmente usadas pela aplicação. Alguns ambientes do SUAP
# podem expor a mesma coleção com pequena variação de caminho; os aliases abaixo
# mantêm a sincronização resiliente sem voltar a usar /api/v2.
ENDPOINT_ALIASES = {
    'pesquisa': ('pesquisa/projetos/',),
    'extensao': ('pesquisa/extensao/', 'extensao/projetos/'),
    'ensino': ('ensino/projetos/', 'ensino/projetos-ensino/'),
}


def _text(item, *keys):
    for key in keys:
        value = item.get(key)
        if value in (None, ''):
            continue
        if isinstance(value, dict):
            nested = value.get('nome') or value.get('name') or value.get('descricao') or value.get('description') or value.get('label') or value.get('value')
            if nested not in (None, ''):
                return nested
        if isinstance(value, (list, tuple)):
            return ', '.join(str(v.get('nome') or v.get('name') or v) if isinstance(v, dict) else str(v) for v in value)
        return value
    return ''


def _campus_match(value):
    s = str(value or '').lower().replace('_', ' ').replace('-', ' ')
    configured = str(current_app.config.get('SUAP_PROJECT_CAMPUS', 'Natal-Zona-Norte')).lower().replace('-', ' ')
    configured = ' '.join(configured.split())
    if configured and configured in ' '.join(s.split()):
        return True
    return any(' '.join(alias.replace('-', ' ').split()) in ' '.join(s.split()) for alias in CAMPUS_ALIASES)


def _normalize_status(value):
    if isinstance(value, dict):
        return _text(value, 'descricao', 'nome', 'label', 'value')
    return str(value or '').strip()


def _is_active(item):
    status = _normalize_status(_text(item, 'status', 'situacao', 'situacao_projeto', 'estado', 'status_projeto')).lower()
    if any(x in status for x in ('cancel', 'finaliz', 'conclu', 'arquiv', 'inativ', 'encerr')):
        return False
    for key in ('ativo', 'active', 'em_execucao', 'em_andamento'):
        if key in item and item[key] is not None:
            return bool(item[key])
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


def _results_page(endpoint, offset, limit=100):
    data = api_get_custom(endpoint, {'limit': limit, 'offset': offset})
    if isinstance(data, list):
        return data, None
    return data.get('results', []), data.get('count')


def _fetch_all(endpoint_candidates, limit=100):
    last_error = None
    for endpoint in endpoint_candidates:
        if endpoint and endpoint.lstrip('/').startswith('v2/'):
            last_error = RuntimeError('Endpoint /api/v2 ignorado: a aplicação utiliza somente a API atual documentada em /api/docs.')
            continue
        try:
            all_results = []
            offset = 0
            while True:
                results, count = _results_page(endpoint, offset, limit)
                all_results.extend(results)
                if not results:
                    break
                offset += len(results)
                if count is not None and offset >= int(count):
                    break
                if len(results) < limit:
                    break
                if offset > 100000:
                    break
            return all_results, endpoint
        except (SuapOAuthError, Exception) as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return [], endpoint_candidates[0]


def sync_projects():
    configured = {
        'pesquisa': current_app.config.get('SUAP_ENDPOINT_PROJECTS_RESEARCH'),
        'extensao': current_app.config.get('SUAP_ENDPOINT_PROJECTS_EXTENSION'),
        'ensino': current_app.config.get('SUAP_ENDPOINT_PROJECTS_TEACHING'),
    }
    imported = []
    errors = []
    for ptype in ('pesquisa', 'ensino', 'extensao'):
        candidates = [configured[ptype]] if configured[ptype] else []
        for candidate in ENDPOINT_ALIASES[ptype]:
            if candidate not in candidates:
                candidates.append(candidate)
        try:
            results, used_endpoint = _fetch_all(candidates)
        except Exception as exc:
            errors.append(f'{ptype}: {exc}')
            continue
        for raw in results:
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
                # Preserve annotations managed in the portal (PIBID, vínculo com a
                # Licenciatura, destaque e publicação) while refreshing SUAP data.
                for key, value in item.items():
                    setattr(project, key, value)
                project.source_system = 'suap'
            project.published = True
            imported.append(project)
    db.session.commit()
    return imported, errors
