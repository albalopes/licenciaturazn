from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required

from app.services.suap import (
    SuapOAuthError,
    current_user_data,
    my_links,
    my_periods,
    my_personal_data,
    my_report,
    my_schedule,
    my_student_data,
    my_virtual_classes,
)

bp = Blueprint("suap", __name__, url_prefix="/suap")


def _api_call(function):
    try:
        return jsonify(function())
    except SuapOAuthError as exc:
        return jsonify({"error": str(exc)}), 502


@bp.get("/meus-dados")
@login_required
def meus_dados():
    return render_template("suap/meus_dados.html", user=current_user)


@bp.get("/api/eu")
@login_required
def eu():
    return _api_call(current_user_data)


@bp.get("/api/vinculos")
@login_required
def vinculos():
    return _api_call(my_links)


@bp.get("/api/dados-pessoais")
@login_required
def dados_pessoais():
    return _api_call(my_personal_data)


@bp.get("/api/dados-aluno")
@login_required
def dados_aluno():
    return _api_call(my_student_data)


@bp.get("/api/periodos")
@login_required
def periodos():
    return _api_call(my_periods)


@bp.get("/api/turmas-virtuais")
@login_required
def turmas_virtuais():
    return _api_call(my_virtual_classes)


@bp.get("/api/boletim/<int:ano>/<int:periodo>")
@login_required
def boletim(ano, periodo):
    return _api_call(lambda: my_report(ano, periodo))


@bp.get("/api/horario/<int:ano>/<int:periodo>")
@login_required
def horario(ano, periodo):
    return _api_call(lambda: my_schedule(ano, periodo))
