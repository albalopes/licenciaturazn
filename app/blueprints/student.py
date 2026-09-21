import json
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, g, session
from flask_login import current_user, login_required

from app.extensions import db
from app.models import EnadeAttempt, EnadeExam, EnadeQuestion
from app.services.student_portal import build_academic_history, fetch_report_history, load_student_portal, demo_student_portal

bp = Blueprint("student", __name__)

DEMO_ENADE_QUESTIONS = [
    {"id": -1, "number": 1, "component": "Questão demonstrativa", "statement": "Em uma atividade de pensamento computacional, decompor um problema significa:", "options": {"A":"dividi-lo em partes menores e tratáveis.","B":"eliminar todos os dados de entrada.","C":"executar o programa sem testar.","D":"substituir o problema por outro.","E":"evitar a identificação de padrões."}, "correct_option":"A"},
    {"id": -2, "number": 2, "component": "Questão demonstrativa", "statement": "Em programação orientada a objetos, encapsulamento está relacionado a:", "options": {"A":"usar apenas variáveis globais.","B":"proteger e organizar o acesso ao estado e comportamento de um objeto.","C":"eliminar métodos.","D":"impedir a criação de classes.","E":"converter código em HTML."}, "correct_option":"B"},
    {"id": -3, "number": 3, "component": "Questão demonstrativa", "statement": "Uma prática coerente com avaliação formativa é:", "options": {"A":"avaliar somente no final do semestre.","B":"usar evidências durante o processo para orientar intervenções pedagógicas.","C":"atribuir a mesma nota independentemente do desempenho.","D":"impedir feedback ao estudante.","E":"desconsiderar os objetivos de aprendizagem."}, "correct_option":"B"},
    {"id": -4, "number": 4, "component": "Questão demonstrativa", "statement": "Uma estrutura de dados adequada para representar uma fila segue, em geral, o princípio:", "options": {"A":"LIFO.","B":"FIFO.","C":"aleatório.","D":"recursivo obrigatório.","E":"ordenamento alfabético."}, "correct_option":"B"},
    {"id": -5, "number": 5, "component": "Questão demonstrativa", "statement": "No contexto de acessibilidade digital, texto alternativo em uma imagem serve principalmente para:", "options": {"A":"aumentar a resolução da imagem.","B":"fornecer uma descrição textual que possa ser interpretada por tecnologias assistivas.","C":"ocultar a imagem de todos os usuários.","D":"substituir o CSS.","E":"reduzir o tamanho do banco de dados."}, "correct_option":"B"},
    {"id": -6, "number": 6, "component": "Questão demonstrativa", "statement": "Em uma rede, o endereço IP é utilizado para:", "options": {"A":"identificar logicamente um dispositivo em uma rede.","B":"armazenar exclusivamente senhas.","C":"definir a resolução do monitor.","D":"substituir o sistema operacional.","E":"criar documentos acadêmicos."}, "correct_option":"A"},
]


@bp.before_request
def mark_demo():
    g.student_demo = request.args.get("demo") == "1" and current_user.is_authenticated and current_user.is_admin

@bp.app_context_processor
def inject_student_demo():
    def student_url(endpoint, **kwargs):
        if getattr(g, "student_demo", False):
            kwargs["demo"] = "1"
        return url_for(endpoint, **kwargs)
    return {"student_url": student_url}


@bp.get("/")
@login_required
def dashboard():
    data = demo_student_portal() if request.args.get("demo") == "1" and current_user.is_admin else load_student_portal()
    return render_template("student/dashboard.html", **data)


@bp.get("/trajetoria")
@login_required
def trajectory():
    data = demo_student_portal() if request.args.get("demo") == "1" and current_user.is_admin else load_student_portal()
    if data.get("demo"):
        cards, progress, errors = data["cards"], data["progress"], []
    else:
        report_history, history_errors = fetch_report_history(data["periods"])
        cards, progress = build_academic_history(data["matrix"], report_history)
        errors = data["errors"] + history_errors
    status_filter = request.args.get("status", "todas")
    if status_filter in {"aprovada", "cursando", "reprovada", "pendente"}:
        visible = [card for card in cards if card["status"] == status_filter]
    else:
        visible = cards
    return render_template(
        "student/trajectory.html",
        **data,
        cards=visible,
        all_cards=cards,
        progress=progress,
        status_filter=status_filter,
        history_errors=errors,
    )


@bp.get("/boletim")
@login_required
def report():
    data = demo_student_portal() if request.args.get("demo") == "1" and current_user.is_admin else load_student_portal()
    selected = request.args.get("period", "")
    selected_period = None
    rows = data["current_report"]
    if selected and "." in selected and not data.get("demo"):
        try:
            year, period = [int(x) for x in selected.split(".", 1)]
            selected_period = {"year": year, "period": period, "label": selected}
            from app.services.suap import my_report
            rows = my_report(year, period)
            if isinstance(rows, dict):
                rows = rows.get("results") or rows.get("data") or []
        except Exception as exc:
            flash(f"Não foi possível consultar o boletim: {exc}", "danger")
    return render_template("student/report.html", **data, rows=rows, selected_period=selected_period)


@bp.get("/horario")
@login_required
def schedule():
    data = demo_student_portal() if request.args.get("demo") == "1" and current_user.is_admin else load_student_portal()
    selected = request.args.get("period", "")
    selected_period = data["current"]
    schedule_data = data["current_schedule"]
    if selected and "." in selected and not data.get("demo"):
        try:
            year, period = [int(x) for x in selected.split(".", 1)]
            selected_period = {"year": year, "period": period, "label": selected}
            from app.services.suap import my_schedule
            schedule_data = my_schedule(year, period)
        except Exception as exc:
            flash(f"Não foi possível consultar o horário: {exc}", "danger")
    from app.services.student_portal import schedule_entries
    selected_entries = data.get("schedule_entries", []) if data.get("demo") else schedule_entries(schedule_data)
    return render_template("student/schedule.html", **data, schedule_data=schedule_data, schedule_entries=selected_entries, selected_period=selected_period)


@bp.get("/turmas")
@login_required
def classes():
    data = demo_student_portal() if request.args.get("demo") == "1" and current_user.is_admin else load_student_portal()
    selected = request.args.get("period", "")
    selected_period = data["current"]
    virtual_classes = data["virtual_classes"]
    if selected and "." in selected and not data.get("demo"):
        try:
            year, period = [int(x) for x in selected.split(".", 1)]
            selected_period = {"year": year, "period": period, "label": selected}
            from app.services.suap import my_virtual_classes
            raw = my_virtual_classes(year, period)
            from app.services.student_portal import _safe_list
            virtual_classes = _safe_list(raw)
        except Exception as exc:
            flash(f"Não foi possível consultar as turmas: {exc}", "danger")
    return render_template("student/classes.html", **data, virtual_classes=virtual_classes, selected_period=selected_period)


@bp.get("/enade")
@login_required
def enade_dashboard():
    demo = request.args.get("demo") == "1" and current_user.is_admin
    exams = EnadeExam.query.filter_by(active=True).order_by(EnadeExam.year.desc()).all()
    exam_id = request.args.get("ano", type=int)
    exam = EnadeExam.query.filter_by(id=exam_id, active=True).first() if exam_id else (exams[0] if exams else None)
    attempts = {}
    if exam and not demo:
        rows = (EnadeAttempt.query.join(EnadeQuestion)
                .filter(EnadeAttempt.user_id == current_user.id, EnadeQuestion.exam_id == exam.id).all())
        attempts = {r.question_id: r for r in rows}
    total = EnadeQuestion.query.filter_by(exam_id=exam.id, active=True).count() if exam else 0
    questions = EnadeQuestion.query.filter_by(exam_id=exam.id, active=True).order_by(EnadeQuestion.number).all() if exam else []
    demo_only_questions = False
    if demo and exam and not questions:
        from types import SimpleNamespace
        questions = [SimpleNamespace(**q, options_json=json.dumps(q["options"], ensure_ascii=False)) for q in DEMO_ENADE_QUESTIONS]
        total = len(questions)
        demo_only_questions = True
    if demo:
        from types import SimpleNamespace
        demo_answers = session.get("demo_enade_answers", {})
        for q in questions:
            selected = demo_answers.get(str(q.id))
            if selected:
                attempts[q.id] = SimpleNamespace(selected_option=selected.get("option"), is_correct=selected.get("is_correct", False), score=selected.get("score", 0.0))
    answered = len(attempts)
    points = sum(a.score for a in attempts.values())
    return render_template("student/enade.html", exams=exams, exam=exam, questions=questions, attempts=attempts, total=total, answered=answered, points=points, demo=demo)


@bp.post("/enade/questao/<int:question_id>")
@login_required
def answer_question(question_id):
    demo = request.form.get("demo") == "1" and current_user.is_admin
    if demo and question_id < 0:
        question_data = next((q for q in DEMO_ENADE_QUESTIONS if q["id"] == question_id), None)
        if not question_data:
            flash("Questão demonstrativa não encontrada.", "danger")
            return redirect(url_for("student.enade_dashboard", demo="1"))
        from types import SimpleNamespace
        question = SimpleNamespace(**question_data, options_json=json.dumps(question_data["options"], ensure_ascii=False))
    else:
        question = EnadeQuestion.query.get_or_404(question_id)
    option = request.form.get("option", "").strip().upper()
    options = json.loads(question.options_json)
    if option not in options:
        flash("Selecione uma alternativa válida.", "warning")
        return redirect(url_for("student.enade_dashboard", ano=(question.exam_id if hasattr(question, "exam_id") else request.args.get("ano", type=int)), demo="1" if demo else None))
    is_correct = bool(question.correct_option and option == question.correct_option)
    score = 1.0 if is_correct else 0.0
    if demo:
        demo_answers = session.get("demo_enade_answers", {})
        demo_answers[str(question.id)] = {"option": option, "is_correct": is_correct, "score": score}
        session["demo_enade_answers"] = demo_answers
        flash("Resposta simulada registrada. Nenhuma informação foi gravada no banco de dados.", "success" if is_correct else "info")
        return redirect(url_for("student.enade_dashboard", ano=(question.exam_id if hasattr(question, "exam_id") else request.args.get("ano", type=int)), demo="1") + f"#questao-{question.id}")
    attempt = EnadeAttempt.query.filter_by(user_id=current_user.id, question_id=question.id).first()
    if not attempt:
        attempt = EnadeAttempt(user_id=current_user.id, question_id=question.id)
        db.session.add(attempt)
    attempt.selected_option = option
    attempt.is_correct = is_correct
    attempt.score = score
    attempt.answered_at = datetime.utcnow()
    db.session.commit()
    if question.correct_option:
        flash("Resposta registrada: " + ("acerto!" if attempt.is_correct else f"a resposta correta é {question.correct_option}."), "success" if attempt.is_correct else "info")
    else:
        flash("Resposta registrada. O gabarito desta questão ainda não está disponível no banco local.", "info")
    return redirect(url_for("student.enade_dashboard", ano=question.exam_id) + f"#questao-{question.id}")
