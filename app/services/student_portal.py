import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import current_app

from app.services.suap import (SuapOAuthError, ensure_access_token, my_periods, my_student_data, my_virtual_classes, my_schedule, my_disciplines, my_completion_requirements, my_frequency, my_upcoming_evaluations, my_calendar, api_get)
from app.models import Matrix, Discipline


def _unwrap(value):
    if isinstance(value, dict):
        for key in ("results", "data", "items", "periodos", "periods"):
            if isinstance(value.get(key), list):
                return value[key]
    return value if isinstance(value, list) else []


def _norm(value):
    text = str(value or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _first(data, keys, default=""):
    if not isinstance(data, dict):
        return default
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return value
    return default


def _student_profile(raw):
    raw = raw or {}
    vinculo = raw.get("vinculo") if isinstance(raw.get("vinculo"), dict) else {}
    merged = {**raw, **vinculo}
    return {
        "name": _first(merged, ["nome_usual", "nome", "name"]),
        "registration": _first(merged, ["matricula", "registration"]),
        "course": _first(merged, ["curso", "curso_nome", "nome_curso"]),
        "campus": _first(merged, ["campus", "campus_nome"]),
        "status": _first(merged, ["situacao", "situacao_matricula", "status"]),
        "matrix_raw": _first(merged, ["matriz", "matriz_curricular", "curriculo", "nome_matriz"]),
        "matrix_year": _first(merged, ["ano_matriz", "matriz_ano", "ano_curriculo"]),
        "current_period": _first(merged, ["periodo_atual", "periodo", "periodo_letivo_atual"]),
        "ira": _first(merged, ["ira", "coeficiente_rendimento", "coeficiente_de_rendimento"]),
        "photo": _first(merged, ["url_foto_75x100", "foto"]),
        "raw": raw,
    }


def identify_local_matrix(profile):
    matrices = Matrix.query.filter_by(is_published=True).order_by(Matrix.year.desc()).all()
    course = _norm(profile.get("course"))
    raw = _norm(profile.get("matrix_raw"))
    year_value = str(profile.get("matrix_year") or "")
    candidates = []
    for matrix in matrices:
        score = 0
        if matrix.year and str(matrix.year) in raw:
            score += 5
        if matrix.year and str(matrix.year) in year_value:
            score += 6
        if score:
            candidates.append((score, matrix))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].year), reverse=True)
    return candidates[0][1]


def normalize_periods(raw):
    rows = _unwrap(raw)
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        year = _first(row, ["ano_letivo", "ano", "year"])
        period = _first(row, ["periodo_letivo", "periodo", "semester"])
        try:
            year = int(year)
            period = int(period)
        except (TypeError, ValueError):
            continue
        key = (year, period)
        if key not in seen:
            seen.add(key)
            result.append({"year": year, "period": period, "label": f"{year}.{period}"})
    return sorted(result, key=lambda x: (x["year"], x["period"]), reverse=True)


def _report_rows(raw):
    rows = _unwrap(raw)
    return [row for row in rows if isinstance(row, dict)]


def _report_name(row):
    return _first(row, ["disciplina", "componente_curricular", "componente", "nome_disciplina", "nome"])


def _report_status(row):
    return str(_first(row, ["situacao", "status", "resultado"])).strip()


def _report_grade(row):
    value = _first(row, ["media_final_disciplina", "media_disciplina", "media_final", "nota_final", "media"])
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _report_frequency(row):
    value = _first(row, ["percentual_carga_horaria_frequentada", "frequencia", "percentual_frequencia"])
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _report_hours(row):
    value = _first(row, ["carga_horaria", "carga_horaria_total", "carga_horaria_cumprida"])
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _discipline_key(name):
    normalized = _norm(name)
    code = ""
    if " - " in normalized:
        code = normalized.split(" - ", 1)[0].strip()
    return code, normalized


def build_academic_history(matrix, report_by_period):
    """Cruza o boletim do SUAP com a matriz local, sem alterar dados do SUAP."""
    if not matrix:
        return [], {"total_hours": 0, "completed_hours": 0, "completed": 0, "total": 0, "percent": 0}

    reports = []
    for period, rows in report_by_period.items():
        for row in rows:
            reports.append({"period": period, "row": row})

    by_code = {}
    by_name = {}
    for item in reports:
        code, normalized = _discipline_key(_report_name(item["row"]))
        if code:
            by_code.setdefault(code, []).append(item)
        by_name.setdefault(normalized, []).append(item)

    cards = []
    required = [d for d in matrix.disciplines if (d.kind or "").lower() != "optativa"]
    for discipline in sorted(matrix.disciplines, key=lambda d: (d.semester or 99, d.name)):
        code = _norm(discipline.code)
        name = _norm(discipline.name)
        matches = by_code.get(code, []) if code else []
        if not matches:
            matches = by_name.get(name, [])
        # Tenta casar pelo trecho após o código, útil quando o SUAP adiciona informações extras.
        if not matches:
            matches = [item for item in reports if name and name in _norm(_report_name(item["row"]))]

        best = matches[-1] if matches else None
        status = "pendente"
        if best:
            raw_status = _norm(_report_status(best["row"]))
            if "aprov" in raw_status or "conclu" in raw_status:
                status = "aprovada"
            elif "matric" in raw_status or "curs" in raw_status or "andamento" in raw_status:
                status = "cursando"
            elif "reprov" in raw_status:
                status = "reprovada"
            else:
                status = "registrada"

        cards.append({
            "discipline": discipline,
            "status": status,
            "grade": _report_grade(best["row"]) if best else None,
            "frequency": _report_frequency(best["row"]) if best else None,
            "period": best["period"] if best else None,
            "suap_name": _report_name(best["row"]) if best else None,
        })

    required_cards = [c for c in cards if c["discipline"] in required]
    total_hours = sum((c["discipline"].hours or 0) for c in required_cards)
    completed_hours = sum((c["discipline"].hours or 0) for c in required_cards if c["status"] == "aprovada")
    total = len(required_cards)
    completed = sum(1 for c in required_cards if c["status"] == "aprovada")
    percent = round((completed_hours / total_hours) * 100, 1) if total_hours else 0
    return cards, {"total_hours": total_hours, "completed_hours": completed_hours, "completed": completed, "total": total, "percent": percent}


def fetch_report_history(periods):
    """Busca boletins em paralelo, usando o mesmo token OAuth já validado."""
    token = ensure_access_token()
    if not token:
        raise SuapOAuthError("No SUAP access token in session.")
    base = current_app.config["SUAP_API_BASE_URL"].rstrip("/")
    endpoint_template = current_app.config["SUAP_ENDPOINT_REPORT"]

    def fetch(item):
        year, period = item["year"], item["period"]
        endpoint = endpoint_template.format(year=year, period=period)
        url = base + "/" + endpoint.lstrip("/")
        response = requests.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=15)
        if response.status_code == 401:
            return item, [], "unauthorized"
        if not response.ok:
            return item, [], f"HTTP {response.status_code}"
        try:
            return item, _report_rows(response.json()), None
        except ValueError:
            return item, [], "JSON inválido"

    result = {}
    errors = []
    max_workers = min(4, max(1, len(periods)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch, item) for item in periods]
        for future in as_completed(futures):
            item, rows, error = future.result()
            result[(item["year"], item["period"])] = rows
            if error:
                errors.append(f"{item['year']}.{item['period']}: {error}")
    return result, errors


def _safe_list(value):
    return _unwrap(value) if isinstance(value, (dict, list)) else []


def _completion_summary(raw):
    if not isinstance(raw, dict):
        return {}
    result = dict(raw)
    for key, value in list(result.items()):
        if isinstance(value, dict):
            for child in ("ch_esperada", "ch_cumprida", "ch_pendente"):
                if child in value:
                    try:
                        value[child] = float(value[child])
                    except (TypeError, ValueError):
                        pass
    try:
        result["percentual_cumprida"] = float(result.get("percentual_cumprida", 0))
    except (TypeError, ValueError):
        result["percentual_cumprida"] = 0
    return result


def _discipline_summary(raw):
    rows = _safe_list(raw)
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append({
            "name": _first(row, ["descricao", "disciplina", "nome"]),
            "code": _first(row, ["sigla", "codigo"]),
            "status": _first(row.get("situacao", {}) if isinstance(row.get("situacao"), dict) else {}, ["rotulo", "status"]) or _first(row, ["situacao", "status"]),
            "frequency": row.get("frequencia"),
            "absences": row.get("qtd_faltas"),
            "hours_total": row.get("ch_total_relogio", row.get("ch_total_aula")),
            "hours_done": row.get("ch_cumprida_aula"),
            "averages": row.get("medias") or [],
            "grades": row.get("notas") or [],
            "raw": row,
        })
    return result


def _evaluation_rows(raw):
    rows = _safe_list(raw)
    result = []
    for row in rows:
        if isinstance(row, dict):
            result.append({
                "discipline": _first(row, ["disciplina", "descricao", "nome"]),
                "title": _first(row, ["descricao_avaliacao", "avaliacao", "nome_avaliacao", "titulo"]),
                "date": _first(row, ["data", "data_avaliacao", "dt_avaliacao"]),
                "raw": row,
            })
    return result


def load_student_portal():
    """Carrega dados do SUAP e os organiza para a experiência do aluno."""
    errors = []
    try:
        raw_student = my_student_data()
    except Exception as exc:
        raw_student = {}
        errors.append(f"dados do aluno: {exc}")
    profile = _student_profile(raw_student)
    if profile.get("photo", "").startswith("/"):
        profile["photo"] = current_app.config["SUAP_BASE_URL"].rstrip("/") + profile["photo"]

    try:
        periods = normalize_periods(my_periods())
    except Exception as exc:
        periods = []
        errors.append(f"períodos: {exc}")

    matrix = identify_local_matrix(profile)
    current = periods[0] if periods else None
    current_report = []
    current_disciplines = []
    current_frequency = {}
    current_schedule = {}
    virtual_classes = []
    upcoming_evaluations = []
    calendar = []

    if current:
        try:
            from app.services.suap import my_report
            current_report = _report_rows(my_report(current["year"], current["period"]))
        except Exception as exc:
            errors.append(f"boletim atual: {exc}")
        try:
            current_disciplines = _discipline_summary(my_disciplines(current["year"], current["period"]))
        except Exception as exc:
            errors.append(f"disciplinas do período: {exc}")
        try:
            current_frequency = my_frequency(current["year"], current["period"]) or {}
        except Exception as exc:
            errors.append(f"frequência do período: {exc}")
        try:
            current_schedule = my_schedule(current["year"], current["period"])
        except Exception as exc:
            errors.append(f"horário: {exc}")
        try:
            virtual_classes = _safe_list(my_virtual_classes(current["year"], current["period"]))
        except Exception as exc:
            errors.append(f"turmas virtuais: {exc}")
        try:
            calendar = _safe_list(my_calendar(current["year"], current["period"]))
        except Exception as exc:
            errors.append(f"calendário acadêmico: {exc}")

    try:
        completion = _completion_summary(my_completion_requirements())
    except Exception as exc:
        completion = {}
        errors.append(f"requisitos de conclusão: {exc}")

    try:
        upcoming_evaluations = _evaluation_rows(my_upcoming_evaluations())
    except Exception as exc:
        errors.append(f"próximas avaliações: {exc}")

    return {
        "profile": profile,
        "periods": periods,
        "matrix": matrix,
        "current": current,
        "current_report": current_report,
        "current_disciplines": current_disciplines,
        "current_frequency": current_frequency,
        "current_schedule": current_schedule,
        "schedule_entries": schedule_entries(current_schedule),
        "virtual_classes": virtual_classes,
        "completion": completion,
        "upcoming_evaluations": upcoming_evaluations,
        "calendar": calendar,
        "errors": errors,
    }


def schedule_entries(raw):
    """Transforma o horário do SUAP em linhas simples para a interface."""
    if not isinstance(raw, dict):
        return []
    days = {1: "Domingo", 2: "Segunda", 3: "Terça", 4: "Quarta", 5: "Quinta", 6: "Sexta", 7: "Sábado"}
    shifts = {"M": "Manhã", "V": "Tarde", "N": "Noite"}
    entries = []
    for day_key, shifts_data in raw.items():
        try:
            day_num = int(day_key)
        except (TypeError, ValueError):
            continue
        if not isinstance(shifts_data, dict):
            continue
        for shift_key, slots in shifts_data.items():
            if not isinstance(slots, dict):
                continue
            for slot_key, slot in slots.items():
                if not isinstance(slot, dict) or not slot.get("aula"):
                    continue
                aula = slot["aula"]
                locations = aula.get("locais_de_aula") or []
                if isinstance(locations, str):
                    locations = [locations]
                entries.append({
                    "day": days.get(day_num, str(day_key)),
                    "day_num": day_num,
                    "shift": shifts.get(str(shift_key), str(shift_key)),
                    "slot": slot_key,
                    "time": slot.get("time", ""),
                    "code": aula.get("sigla", ""),
                    "name": aula.get("descricao", ""),
                    "location": ", ".join(str(x) for x in locations if x),
                    "id": aula.get("id"),
                })
    return sorted(entries, key=lambda x: (x["day_num"], str(x["time"])))


def demo_student_portal():
    """Dados fictícios, somente para a visualização administrativa do portal."""
    from app.models import Matrix
    matrix = Matrix.query.filter_by(year=2018, is_published=True).first() or Matrix.query.order_by(Matrix.year.desc()).first()
    profile = {
        "name": "Mariana Alves de Souza (DEMO)",
        "registration": "20231044010099",
        "course": "Licenciatura em Informática",
        "campus": "IFRN — Natal-Zona Norte",
        "status": "Matriculado",
        "matrix_raw": "PPC 2018 — Licenciatura em Informática",
        "matrix_year": 2018,
        "current_period": "2026.2",
        "ira": 8.7,
        "photo": "",
        "raw": {},
    }
    periods = [{"year": 2026, "period": 2, "label": "2026.2"}, {"year": 2026, "period": 1, "label": "2026.1"}, {"year": 2025, "period": 2, "label": "2025.2"}]
    current = periods[0]
    current_disciplines = [
        {"name": "Pensamento Computacional", "code": "LIC.001", "status": "Cursando", "frequency": 92, "absences": 2, "hours_total": 60, "hours_done": 44, "averages": [], "grades": []},
        {"name": "STEAM e Cultura Maker", "code": "LIC.002", "status": "Cursando", "frequency": 96, "absences": 1, "hours_total": 60, "hours_done": 46, "averages": [], "grades": []},
        {"name": "Estágio Docente IV", "code": "EST.004", "status": "Cursando", "frequency": 100, "absences": 0, "hours_total": 100, "hours_done": 80, "averages": [], "grades": []},
        {"name": "Trabalho de Conclusão de Curso", "code": "TCC", "status": "Cursando", "frequency": 100, "absences": 0, "hours_total": 60, "hours_done": 35, "averages": [], "grades": []},
    ]
    current_report = [
        {"disciplina": "Pensamento Computacional", "situacao": "Cursando", "media_final_disciplina": "8,6", "percentual_carga_horaria_frequentada": 92},
        {"disciplina": "STEAM e Cultura Maker", "situacao": "Cursando", "media_final_disciplina": "9,1", "percentual_carga_horaria_frequentada": 96},
        {"disciplina": "Estágio Docente IV", "situacao": "Cursando", "media_final_disciplina": "9,4", "percentual_carga_horaria_frequentada": 100},
        {"disciplina": "TCC", "situacao": "Cursando", "media_final_disciplina": "8,8", "percentual_carga_horaria_frequentada": 100},
    ]
    completion = {
        "percentual_cumprida": 76.0,
        "regulares_obrigatorios": {"ch_esperada": 2500, "ch_cumprida": 1900, "ch_pendente": 600},
        "regulares_optativos": {"ch_esperada": 180, "ch_cumprida": 120, "ch_pendente": 60},
        "atividades_pratica_profissional": {"ch_esperada": 600, "ch_cumprida": 520, "ch_pendente": 80},
        "seminarios": {"ch_esperada": 60, "ch_cumprida": 60, "ch_pendente": 0},
    }
    schedule_entries = [
        {"day": "Segunda", "time": "18:50–20:30", "code": "LIC.001", "name": "Pensamento Computacional", "location": "LabMaker"},
        {"day": "Terça", "time": "18:50–20:30", "code": "LIC.002", "name": "STEAM e Cultura Maker", "location": "LabMaker"},
        {"day": "Quarta", "time": "20:40–22:20", "code": "TCC", "name": "Orientação de TCC", "location": "Sala 12"},
    ]
    virtual_classes = [
        {"sigla": "LIC.001", "ano_letivo": 2026, "periodo_letivo": 2, "descricao": "Pensamento Computacional", "horarios_de_aula": "Segunda, 18:50", "locais_de_aula": "LabMaker"},
        {"sigla": "LIC.002", "ano_letivo": 2026, "periodo_letivo": 2, "descricao": "STEAM e Cultura Maker", "horarios_de_aula": "Terça, 18:50", "locais_de_aula": "LabMaker"},
    ]
    upcoming_evaluations = [
        {"discipline": "Pensamento Computacional", "title": "Atividade avaliativa", "date": "24/09/2026"},
        {"discipline": "STEAM e Cultura Maker", "title": "Projeto Maker", "date": "30/09/2026"},
        {"discipline": "TCC", "title": "Entrega da versão para orientação", "date": "02/10/2026"},
    ]
    cards = []
    if matrix:
        statuses = ["aprovada", "aprovada", "aprovada", "cursando", "pendente", "aprovada", "aprovada", "pendente"]
        for idx, d in enumerate(sorted(matrix.disciplines, key=lambda x: (x.semester or 99, x.name))):
            status = statuses[idx % len(statuses)]
            cards.append({"discipline": d, "status": status, "grade": 8.0 + (idx % 9) / 10 if status == "aprovada" else (8.8 if status == "cursando" else None), "frequency": 90 + (idx % 10) if status in ("aprovada", "cursando") else None, "period": (2025, 2) if status == "aprovada" else ((2026, 2) if status == "cursando" else None), "suap_name": d.name})
        required = [c for c in cards if (c["discipline"].kind or "").lower() != "optativa"]
        total_hours = sum(c["discipline"].hours or 0 for c in required)
        completed_hours = sum(c["discipline"].hours or 0 for c in required if c["status"] == "aprovada")
        progress = {"total_hours": total_hours, "completed_hours": completed_hours, "completed": sum(c["status"] == "aprovada" for c in required), "total": len(required), "percent": round(completed_hours * 100 / total_hours, 1) if total_hours else 0}
    else:
        cards, progress = [], {"total_hours": 0, "completed_hours": 0, "completed": 0, "total": 0, "percent": 0}
    return {"profile": profile, "periods": periods, "matrix": matrix, "current": current, "current_report": current_report, "current_disciplines": current_disciplines, "current_frequency": {}, "current_schedule": {}, "schedule_entries": schedule_entries, "virtual_classes": virtual_classes, "upcoming_evaluations": upcoming_evaluations, "calendar": [], "completion": completion, "errors": [], "cards": cards, "progress": progress, "demo": True}
