from flask import Blueprint, render_template, request, jsonify

from app.services.chatbot import answer_question

bp = Blueprint("chatbot", __name__)


@bp.get("/")
def chat_page():
    return render_template("chatbot/index.html")


@bp.post("/ask")
def ask():
    data = request.get_json(silent=True) or request.form
    question = (data.get("question") or "").strip()
    matrix_year = data.get("matrix_year")
    try:
        matrix_year = int(matrix_year) if matrix_year else None
    except (TypeError, ValueError):
        matrix_year = None

    if not question:
        return jsonify({"error": "Digite uma pergunta."}), 400
    if len(question) > 1200:
        return jsonify({"error": "A pergunta deve ter no máximo 1200 caracteres."}), 400

    result = answer_question(question, matrix_year=matrix_year)
    return jsonify(result)
