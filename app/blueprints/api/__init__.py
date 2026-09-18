from flask import Blueprint, jsonify, request

from app.models import Discipline, Matrix

bp = Blueprint("api", __name__)


@bp.get("/matrizes/<int:year>/disciplinas")
def disciplines(year):
    matrix = Matrix.query.filter_by(year=year, is_published=True).first_or_404()
    items = Discipline.query.filter_by(matrix_id=matrix.id).order_by(Discipline.semester, Discipline.name).all()
    return jsonify({
        "matrix": {"year": matrix.year, "title": matrix.title},
        "items": [
            {
                "id": d.id,
                "code": d.code,
                "name": d.name,
                "semester": d.semester,
                "area": d.area,
                "kind": d.kind,
                "credits": d.credits,
                "hours": d.hours,
            }
            for d in items
        ],
    })
