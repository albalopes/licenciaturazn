from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app, g, Response
from math import ceil
from datetime import datetime
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AcademicEvent, Discipline, Document, Matrix, Project, SitePage, Teacher, KnowledgeSource, GovernanceMember, GovernanceDocument, EntranceSchedule, FAQ, EnadeExam, EnadeQuestion, EnadeAttempt, User, MemoriaWork, TeachingAssignment, CourseCoordinator

bp = Blueprint("admin", __name__)

RESOURCE_ENDPOINTS = {"matrizes":"matrices", "disciplinas":"disciplines", "docentes":"teachers", "paginas":"pages", "documentos":"documents", "eventos":"events", "projetos":"projects", "entradas":"entrance_management", "faq":"faq_management", "portarias":"governance_management", "membros-governanca":"governance_management", "coordenadores":"coordinators_management", "conhecimento":"knowledge_management"}

RESOURCE_CONFIG = {
    "matrizes": {"model": Matrix, "label": "Matriz", "fields": [
        ("year", "Ano", "number"), ("title", "Título", "text"), ("status", "Status", "text"), ("description", "Descrição", "textarea"),
        ("document_url", "Documento (URL)", "url"), ("duration_semesters", "Semestres", "number"), ("total_hours", "Carga horária", "number"), ("is_published", "Publicada", "checkbox")],
    },
    "coordenadores": {"model": CourseCoordinator, "label": "Coordenador(a) anterior", "fields": [
        ("name", "Nome", "text"), ("start_year", "Ano inicial", "number"), ("end_year", "Ano final", "number"),
        ("role", "Função", "text"), ("profile_url", "Página/perfil", "url"), ("notes", "Observações", "textarea"), ("active", "Publicado", "checkbox")],
    },
    "disciplinas": {"model": Discipline, "label": "Disciplina", "fields": [
        ("matrix_id", "Matriz", "matrix"), ("code", "Código", "text"), ("name", "Nome", "text"), ("semester", "Semestre", "number"),
        ("area", "Área", "text"), ("kind", "Tipo", "text"), ("credits", "Créditos", "number"), ("hours", "Horas", "number"), ("lesson_hours", "Horas-aula", "number"),
        ("summary", "Ementa", "textarea"), ("objectives", "Objetivos", "textarea"), ("contents", "Conteúdos", "textarea"), ("methodology", "Metodologia", "textarea"),
        ("assessment", "Avaliação", "textarea"), ("bibliography_basic", "Bibliografia básica", "textarea"), ("bibliography_complementary", "Bibliografia complementar", "textarea"), ("support_software", "Softwares", "textarea")],
    },
    "docentes": {"model": Teacher, "label": "Docente", "fields": [
        ("name", "Nome", "text"), ("siape", "SIAPE/matrícula", "text"), ("ingresso_disciplina", "Disciplina de ingresso", "text"), ("photo_url", "Foto (URL)", "url"), ("email", "E-mail", "email"), ("lattes_url", "Lattes", "url"), ("orcid_url", "ORCID", "url"),
        ("education", "Formação", "textarea"), ("areas", "Áreas", "textarea"), ("bio", "Biografia", "textarea"), ("active", "Ativo", "checkbox")],
    },
    "paginas": {"model": SitePage, "label": "Página", "fields": [("slug","Slug","text"),("title","Título","text"),("category","Categoria","text"),("content","Conteúdo","textarea"),("published","Publicada","checkbox")]},
    "documentos": {"model": Document, "label": "Documento", "fields": [("title","Título","text"),("category","Categoria","text"),("description","Descrição","textarea"),("url","URL","url"),("published","Publicado","checkbox")]},
    "eventos": {"model": AcademicEvent, "label": "Evento", "fields": [("title","Título","text"),("description","Descrição","textarea"),("starts_at","Início","datetime"),("ends_at","Fim","datetime"),("category","Categoria","text"),("url","URL","url"),("published","Publicado","checkbox")]},
    "projetos": {"model": Project, "label": "Projeto", "fields": [("title","Título","text"),("acronym","Sigla","text"),("project_type","Tipo","text"),("description","Descrição","textarea"),("objectives","Objetivos","textarea"),("coordinator","Coordenador","text"),("team","Equipe","textarea"),("period","Período","text"),("status","Status","text"),("campus","Campus","text"),("academic_year","Ano","number"),("funding","Fomento","text"),("partners","Parceiros","textarea"),("url","URL","url"),("image_url","Imagem","url"),("is_pibid","PIBID","checkbox"),("has_licenciatura_students","Alunos da Licenciatura","nullable_checkbox"),("licenciatura_notes","Observação sobre alunos","textarea"),("featured","Destaque","checkbox"),("published","Publicado","checkbox")]},
    "entradas": {"model": EntranceSchedule, "label": "Entrada", "fields": [("year","Ano","number"),("shift","Turno","text"),("matrix_year","Matriz","number"),("notes","Observações","textarea"),("published","Publicada","checkbox")]},
    "faq": {"model": FAQ, "label": "FAQ", "fields": [("question","Pergunta","text"),("answer","Resposta","textarea"),("category","Categoria","text"),("position","Posição","number"),("published","Publicada","checkbox")]},
    "portarias": {"model": GovernanceDocument, "label": "Portaria", "fields": [("body","Órgão","text"),("title","Título","text"),("portaria_number","Número da portaria","text"),("issued_at","Data de emissão","date"),("semester","Semestre","text"),("document_url","Documento (URL)","url"),("active","Vigente","checkbox")]},
    "membros-governanca": {"model": GovernanceMember, "label": "Membro de governança", "fields": [("body","Órgão","text"),("name","Nome","text"),("role","Função","text"),("term","Mandato","text"),("siape","Matrícula/SIAPE","text"),("substitute","Suplente","checkbox"),("semester","Semestre","text"),("active","Ativo","checkbox")]},
    "conhecimento": {"model": KnowledgeSource, "label": "Fonte de conhecimento", "fields": [("title","Título","text"),("document_type","Tipo","text"),("matrix_year","Ano da matriz","number"),("description","Descrição","textarea"),("source_url","URL da fonte","url"),("active","Ativa","checkbox")]},
}

def _paginate(query):
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 5), 100)
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    # Expose the current pagination object to the shared admin pagination
    # partial. The resource templates keep their resource-specific variable
    # (matrices, disciplines, projects, etc.) while the partial uses
    # ``pagination`` for the navigation controls.
    g.admin_pagination = pagination
    return pagination


@bp.app_context_processor
def inject_admin_pagination():
    return {"pagination": getattr(g, "admin_pagination", None)}


def _apply_search(query, model, fields):
    q = request.args.get("q", "").strip()
    if q:
        from sqlalchemy import or_
        text_fields = [getattr(model, f) for f in fields if hasattr(getattr(model, f), 'type') and f not in ('id',)]
        query = query.filter(or_(*[field.ilike(f"%{q}%") for field in text_fields if hasattr(field, 'ilike')])) if text_fields else query
    return query, q


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped




@bp.get("/visao-aluno")
@admin_required
def student_preview():
    return redirect(url_for("student.dashboard", demo="1"))


@bp.get("/enade/resultados")
@admin_required
def enade_results():
    exams = EnadeExam.query.filter_by(active=True).order_by(EnadeExam.year.desc()).all()
    selected_exam = request.args.get("ano", type=int)
    exam = EnadeExam.query.filter_by(id=selected_exam).first() if selected_exam else (exams[0] if exams else None)
    results = []
    if exam:
        rows = (db.session.query(EnadeAttempt, EnadeQuestion, User)
                .join(EnadeQuestion, EnadeAttempt.question_id == EnadeQuestion.id)
                .join(User, EnadeAttempt.user_id == User.id)
                .filter(EnadeQuestion.exam_id == exam.id)
                .all())
        grouped = {}
        for attempt, question, user in rows:
            item = grouped.setdefault(user.id, {"user": user, "answered": 0, "correct": 0, "points": 0.0, "last": None})
            item["answered"] += 1
            item["correct"] += int(bool(attempt.is_correct))
            item["points"] += float(attempt.score or 0)
            if item["last"] is None or attempt.answered_at > item["last"]:
                item["last"] = attempt.answered_at
        total = EnadeQuestion.query.filter_by(exam_id=exam.id, active=True).count()
        for item in grouped.values():
            item["total"] = total
            item["accuracy"] = round(item["correct"] * 100 / item["answered"], 1) if item["answered"] else 0
            item["completion"] = round(item["answered"] * 100 / total, 1) if total else 0
        results = sorted(grouped.values(), key=lambda x: (x["points"], x["accuracy"], x["answered"]), reverse=True)
    return render_template("admin/enade_results.html", exams=exams, exam=exam, results=results)


@bp.get("/enade/resultados.csv")
@admin_required
def enade_results_csv():
    import csv, io
    exam = EnadeExam.query.filter_by(id=request.args.get("ano", type=int)).first() if request.args.get("ano") else EnadeExam.query.order_by(EnadeExam.year.desc()).first()
    if not exam:
        return Response("", mimetype="text/csv")
    rows = (db.session.query(EnadeAttempt, EnadeQuestion, User)
            .join(EnadeQuestion, EnadeAttempt.question_id == EnadeQuestion.id)
            .join(User, EnadeAttempt.user_id == User.id)
            .filter(EnadeQuestion.exam_id == exam.id).all())
    grouped = {}
    for attempt, question, user in rows:
        item = grouped.setdefault(user.id, {"name": user.name, "registration": user.registration or "", "answered": 0, "correct": 0, "points": 0.0, "last": None})
        item["answered"] += 1; item["correct"] += int(bool(attempt.is_correct)); item["points"] += float(attempt.score or 0)
        if item["last"] is None or attempt.answered_at > item["last"]: item["last"] = attempt.answered_at
    out=io.StringIO(); w=csv.writer(out); w.writerow(["ano","aluno","matricula","questoes_respondidas","acertos","aproveitamento_percentual","pontos","ultima_resposta"])
    for item in sorted(grouped.values(), key=lambda x: x["name"]):
        accuracy=round(item["correct"]*100/item["answered"],1) if item["answered"] else 0
        w.writerow([exam.year,item["name"],item["registration"],item["answered"],item["correct"],accuracy,item["points"],item["last"].isoformat() if item["last"] else ""])
    return Response("\ufeff"+out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=enade_{exam.year}_resultados.csv"})


@bp.get("/enade/resultados-anonimo.csv")
@admin_required
def enade_results_anonymous_csv():
    import csv, io, hashlib
    exam = EnadeExam.query.filter_by(id=request.args.get("ano", type=int)).first() if request.args.get("ano") else EnadeExam.query.order_by(EnadeExam.year.desc()).first()
    if not exam:
        return Response("", mimetype="text/csv")
    rows = (db.session.query(EnadeAttempt, EnadeQuestion, User)
            .join(EnadeQuestion, EnadeAttempt.question_id == EnadeQuestion.id)
            .join(User, EnadeAttempt.user_id == User.id)
            .filter(EnadeQuestion.exam_id == exam.id).all())
    grouped = {}
    for attempt, question, user in rows:
        key = hashlib.sha256(str(user.id).encode()).hexdigest()[:10]
        item = grouped.setdefault(key, {"answered": 0, "correct": 0, "points": 0.0})
        item["answered"] += 1; item["correct"] += int(bool(attempt.is_correct)); item["points"] += float(attempt.score or 0)
    out=io.StringIO(); w=csv.writer(out); w.writerow(["ano","participante","questoes_respondidas","acertos","aproveitamento_percentual","pontos"])
    for i,item in enumerate(grouped.values(),1):
        accuracy=round(item["correct"]*100/item["answered"],1) if item["answered"] else 0
        w.writerow([exam.year,f"Participante {i:03d}",item["answered"],item["correct"],accuracy,item["points"]])
    return Response("\ufeff"+out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=enade_{exam.year}_resultados_anonimos.csv"})


@bp.route("/horarios", methods=["GET", "POST"])
@admin_required
def schedule_management():
    if request.method == "POST":
        teacher = Teacher.query.get(request.form.get("teacher_id", type=int))
        if not teacher:
            flash("Selecione um docente válido.", "danger")
            return redirect(url_for("admin.schedule_management"))
        db.session.add(TeachingAssignment(
            teacher_id=teacher.id, teacher_name=teacher.name,
            semester=request.form["semester"], course=request.form["course"],
            class_code=request.form.get("class_code"), weekday=request.form["weekday"],
            start_time=request.form["start_time"], end_time=request.form["end_time"],
            room=request.form.get("room"), source=request.form.get("source") or "Cadastro administrativo"
        ))
        db.session.commit()
        flash("Registro de horário adicionado ao histórico.", "success")
        return redirect(url_for("admin.schedule_management"))
    semester=request.args.get("semestre", "")
    query=TeachingAssignment.query.join(Teacher, isouter=True).order_by(TeachingAssignment.semester.desc(), TeachingAssignment.weekday, TeachingAssignment.start_time)
    if semester:
        query=query.filter(TeachingAssignment.semester==semester)
    assignments=query.all()
    return render_template("admin/schedule.html", assignments=assignments, teachers=Teacher.query.filter_by(active=True).order_by(Teacher.name).all(), semester=semester)

@bp.post("/horarios/importar-2026-2")
@admin_required
def import_schedule_2026_2():
    from pathlib import Path
    import json
    path=Path(current_app.root_path).parent / "data" / "licenciatura_horarios_2026_2.json"
    if not path.exists():
        flash("Arquivo de horário não encontrado no projeto.", "danger")
        return redirect(url_for("admin.schedule_management"))
    items=json.loads(path.read_text(encoding="utf-8"))
    TeachingAssignment.query.filter_by(semester="2026.2").delete(synchronize_session=False)
    for item in items:
        for name in [n.strip() for n in item["teacher"].split("/")]:
            teacher=Teacher.query.filter(Teacher.name.ilike(name)).first()
            if not teacher:
                teacher=Teacher(name=name, active=True); db.session.add(teacher); db.session.flush()
            db.session.add(TeachingAssignment(teacher_id=teacher.id, teacher_name=teacher.name, semester="2026.2", course=item["course"], class_code=item["class_code"], weekday=item["weekday"], start_time=item["start_time"], end_time=item["end_time"], room=item.get("room"), source="horário 2026.2 ZN - turmas v4.pdf"))
    db.session.commit()
    flash(f"Horário da Licenciatura 2026.2 importado: {len(items)} registros de turma.", "success")
    return redirect(url_for("admin.schedule_management"))

@bp.route("/memoria", methods=["GET", "POST"])
@admin_required
def memoria_management():
    result = None
    if request.method == "POST":
        from app.services.memoria import sync_memoria
        try:
            result = sync_memoria()
            flash(f"Memoria sincronizado: {result['created']} novos, {result['updated']} atualizados e {len(result['errors'])} ocorrências com erro.", "success" if not result["errors"] else "warning")
        except Exception as exc:
            flash(f"Não foi possível sincronizar o Memoria: {exc}", "danger")
    works = MemoriaWork.query.filter_by(active=True).order_by(MemoriaWork.date.desc(), MemoriaWork.title).all()
    return render_template("admin/memoria.html", works=works, result=result)

@bp.get("/")
@admin_required
def dashboard():
    counts = {
        "matrices": Matrix.query.count(),
        "disciplinas": Discipline.query.count(),
        "docentes": Teacher.query.count(),
        "paginas": SitePage.query.count(),
        "documentos": Document.query.count(),
        "eventos": AcademicEvent.query.count(),
        "conhecimento": KnowledgeSource.query.count(),
        "projetos": Project.query.count(),
        "enade": EnadeQuestion.query.count(),
    }
    return render_template("admin/dashboard.html", counts=counts)


@bp.route("/matrizes", methods=["GET", "POST"])
@admin_required
def matrices():
    if request.method == "POST":
        matrix = Matrix(
            year=request.form["year"], title=request.form["title"], status=request.form.get("status", "historica"),
            description=request.form.get("description"), document_url=request.form.get("document_url"),
            duration_semesters=request.form.get("duration_semesters", type=int), total_hours=request.form.get("total_hours", type=int),
            is_published=bool(request.form.get("is_published")),
        )
        db.session.add(matrix)
        db.session.commit()
        flash("Matriz criada.", "success")
        return redirect(url_for("admin.matrices"))
    q=request.args.get("q", "").strip(); query=Matrix.query.order_by(Matrix.year.desc());
    if q: query=query.filter(Matrix.title.ilike(f"%{q}%"))
    return render_template("admin/matrices.html", matrices=_paginate(query), q=q)


@bp.post("/matrizes/<int:matrix_id>/excluir")
@admin_required
def delete_matrix(matrix_id):
    matrix = Matrix.query.get_or_404(matrix_id)
    db.session.delete(matrix)
    db.session.commit()
    flash("Matriz excluída.", "success")
    return redirect(url_for("admin.matrices"))


@bp.route("/disciplinas", methods=["GET", "POST"])
@admin_required
def disciplines():
    if request.method == "POST":
        d = Discipline(
            matrix_id=request.form["matrix_id"], code=request.form.get("code"), name=request.form["name"],
            semester=request.form.get("semester", type=int), area=request.form.get("area"), kind=request.form.get("kind", "obrigatoria"),
            credits=request.form.get("credits", type=int), hours=request.form.get("hours", type=int),
            lesson_hours=request.form.get("lesson_hours", type=int), summary=request.form.get("summary"),
            objectives=request.form.get("objectives"), contents=request.form.get("contents"), methodology=request.form.get("methodology"),
            assessment=request.form.get("assessment"), bibliography_basic=request.form.get("bibliography_basic"),
            bibliography_complementary=request.form.get("bibliography_complementary"), support_software=request.form.get("support_software"),
        )
        db.session.add(d)
        db.session.commit()
        flash("Disciplina cadastrada.", "success")
        return redirect(url_for("admin.disciplines"))
    q=request.args.get("q", "").strip(); query=Discipline.query.order_by(Discipline.matrix_id, Discipline.semester, Discipline.name);
    if q: query=query.filter(Discipline.name.ilike(f"%{q}%"))
    return render_template("admin/disciplines.html", disciplines=_paginate(query), matrices=Matrix.query.order_by(Matrix.year.desc()).all(), q=q)


@bp.post("/disciplinas/<int:discipline_id>/excluir")
@admin_required
def delete_discipline(discipline_id):
    d = Discipline.query.get_or_404(discipline_id)
    db.session.delete(d)
    db.session.commit()
    flash("Disciplina excluída.", "success")
    return redirect(url_for("admin.disciplines"))


@bp.route("/docentes", methods=["GET", "POST"])
@admin_required
def teachers():
    if request.method == "POST":
        teacher = Teacher(
            name=request.form["name"], siape=request.form.get("siape"), suap_id=request.form.get("siape"), ingresso_disciplina=request.form.get("ingresso_disciplina"), photo_url=request.form.get("photo_url"), email=request.form.get("email"),
            lattes_url=request.form.get("lattes_url"), orcid_url=request.form.get("orcid_url"), education=request.form.get("education"),
            areas=request.form.get("areas"), bio=request.form.get("bio"), active=bool(request.form.get("active")),
        )
        db.session.add(teacher)
        db.session.commit()
        flash("Docente cadastrado.", "success")
        return redirect(url_for("admin.teachers"))
    q=request.args.get("q", "").strip(); ativo=request.args.get("ativo", "").strip().lower(); query=Teacher.query.order_by(Teacher.name)
    if q:
        from sqlalchemy import or_
        query=query.filter(or_(Teacher.name.ilike(f"%{q}%"), Teacher.email.ilike(f"%{q}%"), Teacher.siape.ilike(f"%{q}%")))
    if ativo == "sim": query=query.filter_by(active=True)
    elif ativo == "nao": query=query.filter_by(active=False)
    return render_template("admin/teachers.html", teachers=_paginate(query), q=q)


@bp.route("/paginas", methods=["GET", "POST"])
@admin_required
def pages():
    if request.method == "POST":
        page = SitePage(slug=request.form["slug"], title=request.form["title"], category=request.form.get("category"), content=request.form.get("content"), published=bool(request.form.get("published")))
        db.session.add(page)
        db.session.commit()
        flash("Página criada.", "success")
        return redirect(url_for("admin.pages"))
    q=request.args.get("q", "").strip(); query=SitePage.query.order_by(SitePage.title);
    if q: query=query.filter(SitePage.title.ilike(f"%{q}%"))
    return render_template("admin/pages.html", pages=_paginate(query), q=q)


@bp.route("/documentos", methods=["GET", "POST"])
@admin_required
def documents():
    if request.method == "POST":
        document = Document(title=request.form["title"], category=request.form["category"], description=request.form.get("description"), url=request.form["url"], published=bool(request.form.get("published")))
        db.session.add(document)
        db.session.commit()
        flash("Documento cadastrado.", "success")
        return redirect(url_for("admin.documents"))
    q=request.args.get("q", "").strip(); query=Document.query.order_by(Document.published_at.desc());
    if q: query=query.filter(Document.title.ilike(f"%{q}%"))
    return render_template("admin/documents.html", documents=_paginate(query), q=q)


@bp.route("/eventos", methods=["GET", "POST"])
@admin_required
def events():
    if request.method == "POST":
        from datetime import datetime
        event = AcademicEvent(title=request.form["title"], description=request.form.get("description"), starts_at=datetime.fromisoformat(request.form["starts_at"]), ends_at=datetime.fromisoformat(request.form["ends_at"]) if request.form.get("ends_at") else None, category=request.form.get("category"), url=request.form.get("url"), published=bool(request.form.get("published")))
        db.session.add(event)
        db.session.commit()
        flash("Evento cadastrado.", "success")
        return redirect(url_for("admin.events"))
    q=request.args.get("q", "").strip(); query=AcademicEvent.query.order_by(AcademicEvent.starts_at.desc());
    if q: query=query.filter(AcademicEvent.title.ilike(f"%{q}%"))
    return render_template("admin/events.html", events=_paginate(query), q=q)

@bp.route("/coordenadores", methods=["GET", "POST"])
@login_required
def coordinators_management():
    if not current_user.is_admin:
        abort(403)
    if request.method == "POST":
        obj = CourseCoordinator(
            name=request.form.get("name", "").strip(),
            start_year=int(request.form.get("start_year") or 0),
            end_year=int(request.form.get("end_year")) if request.form.get("end_year") else None,
            role=request.form.get("role") or "Coordenador(a) do curso",
            profile_url=request.form.get("profile_url") or None,
            notes=request.form.get("notes") or None,
            active=bool(request.form.get("active")),
        )
        if not obj.name or not obj.start_year:
            flash("Informe nome e ano inicial.", "error")
        else:
            db.session.add(obj)
            db.session.commit()
            flash("Histórico de coordenação salvo.", "success")
            return redirect(url_for("admin.coordinators_management"))
    coordinators = CourseCoordinator.query.order_by(CourseCoordinator.start_year.desc(), CourseCoordinator.name).all()
    return render_template("admin/coordinators.html", coordinators=coordinators)


@bp.route("/gestao", methods=["GET", "POST"])
@admin_required
def governance_management():
    q=request.args.get("q", "").strip()
    body=request.args.get("body", "").strip()
    query=GovernanceDocument.query.order_by(GovernanceDocument.issued_at.desc(), GovernanceDocument.id.desc())
    if body in ("colegiado", "nde"): query=query.filter_by(body=body)
    if q: query=query.filter(GovernanceDocument.title.ilike(f"%{q}%") | GovernanceDocument.portaria_number.ilike(f"%{q}%"))
    documents=_paginate(query)
    member_page=max(request.args.get("m_page", 1, type=int), 1)
    member_q=request.args.get("mq", "").strip()
    member_query=GovernanceMember.query.order_by(GovernanceMember.body, GovernanceMember.semester.desc(), GovernanceMember.name)
    if body in ("colegiado", "nde"):
        member_query=member_query.filter_by(body=body)
    if member_q:
        from sqlalchemy import or_
        member_query=member_query.filter(or_(GovernanceMember.name.ilike(f"%{member_q}%"), GovernanceMember.siape.ilike(f"%{member_q}%"), GovernanceMember.role.ilike(f"%{member_q}%")))
    members=db.paginate(member_query, page=member_page, per_page=20, error_out=False)
    return render_template("admin/governance.html", documents=documents, members=members, q=q, body=body, member_q=member_q)


@bp.post("/governanca/<int:document_id>/excluir")
@admin_required
def delete_governance_document(document_id):
    from pathlib import Path
    doc = GovernanceDocument.query.get_or_404(document_id)
    path = Path(doc.file_path) if doc.file_path else None
    TeacherHistory.query.filter_by(governance_document_id=doc.id).update({"governance_document_id": None})
    db.session.delete(doc); db.session.commit()
    if path:
        try: path.unlink()
        except OSError: pass
    flash("Portaria removida do histórico.", "success")
    return redirect(url_for("admin.governance_management"))


@bp.post("/governanca/membros/<int:member_id>/excluir")
@admin_required
def delete_governance_member(member_id):
    member = GovernanceMember.query.get_or_404(member_id)
    db.session.delete(member); db.session.commit()
    flash("Membro removido do histórico.", "success")
    return redirect(url_for("admin.governance_management"))


@bp.route("/ingressos", methods=["GET", "POST"])
@admin_required
def entrance_management():
    from app.models import EntranceSchedule
    if request.method == "POST":
        entry = EntranceSchedule(year=request.form["year"], shift=request.form["shift"], matrix_year=request.form.get("matrix_year", type=int), notes=request.form.get("notes"), published=bool(request.form.get("published")))
        db.session.add(entry)
        db.session.commit()
        flash("Entrada cadastrada.", "success")
        return redirect(url_for("admin.entrance_management"))
    q=request.args.get("q", "").strip(); query=EntranceSchedule.query.order_by(EntranceSchedule.year.desc());
    if q: query=query.filter(EntranceSchedule.shift.ilike(f"%{q}%"))
    return render_template("admin/entrances.html", entries=_paginate(query), q=q)


@bp.route("/faq", methods=["GET", "POST"])
@admin_required
def faq_management():
    from app.models import FAQ
    if request.method == "POST":
        item = FAQ(question=request.form["question"], answer=request.form["answer"], category=request.form.get("category"), position=request.form.get("position", 0, type=int), published=bool(request.form.get("published")))
        db.session.add(item)
        db.session.commit()
        flash("Pergunta cadastrada.", "success")
        return redirect(url_for("admin.faq_management"))
    q=request.args.get("q", "").strip(); query=FAQ.query.order_by(FAQ.category, FAQ.position);
    if q: query=query.filter(FAQ.question.ilike(f"%{q}%"))
    return render_template("admin/faq.html", faqs=_paginate(query), q=q)


@bp.route("/<resource>/<int:object_id>/editar", methods=["GET", "POST"])
@admin_required
def edit_resource(resource, object_id):
    config = RESOURCE_CONFIG.get(resource)
    if not config:
        abort(404)
    obj = config["model"].query.get_or_404(object_id)
    if request.method == "POST":
        for field, _label, kind in config["fields"]:
            if kind == "checkbox":
                setattr(obj, field, bool(request.form.get(field)))
            elif kind == "nullable_checkbox":
                value = request.form.get(field)
                setattr(obj, field, None if value in (None, "") else value == "true")
            elif kind == "number":
                raw = request.form.get(field)
                setattr(obj, field, int(raw) if raw not in (None, "") else None)
            elif kind == "datetime":
                raw = request.form.get(field)
                setattr(obj, field, datetime.fromisoformat(raw) if raw else None)
            elif kind == "date":
                raw = request.form.get(field)
                setattr(obj, field, datetime.fromisoformat(raw).date() if raw else None)
            elif kind == "matrix":
                setattr(obj, field, int(request.form[field]))
            else:
                setattr(obj, field, request.form.get(field))
        db.session.commit()
        flash(f"{config['label']} atualizado(a).", "success")
        return redirect(url_for("admin." + RESOURCE_ENDPOINTS[resource]))
    context = {}
    if resource == "disciplinas":
        context["matrices"] = Matrix.query.order_by(Matrix.year.desc()).all()
    context["RESOURCE_ENDPOINTS"] = RESOURCE_ENDPOINTS
    return render_template("admin/edit_resource.html", resource=resource, config=config, obj=obj, **context)


@bp.post("/<resource>/<int:object_id>/excluir")
@admin_required
def delete_resource(resource, object_id):
    config = RESOURCE_CONFIG.get(resource)
    if not config:
        abort(404)
    obj = config["model"].query.get_or_404(object_id)
    if resource == "portarias":
        TeacherHistory.query.filter_by(governance_document_id=obj.id).update({"governance_document_id": None})
    db.session.delete(obj)
    db.session.commit()
    flash(f"{config['label']} excluído(a).", "success")
    return redirect(url_for("admin." + RESOURCE_ENDPOINTS[resource]))


@bp.post("/projetos/sincronizar-suap")
@admin_required
def sync_projects_suap():
    from app.services.projects import sync_projects
    imported, errors = sync_projects()
    if errors:
        flash(f"Sincronização parcial: {len(imported)} projeto(s) importado(s). {'; '.join(errors)}", "warning")
    else:
        flash(f"Sincronização concluída: {len(imported)} projeto(s) de Pesquisa/Extensão do Campus Natal-Zona Norte importado(s) a partir da API /api/.", "success")
    return redirect(url_for("admin.projects"))


@bp.route("/governanca/importar", methods=["POST"])
@admin_required
def import_governance_document():
    from pathlib import Path
    from app.services.governance import import_governance
    uploaded = request.files.get("file")
    body = request.form.get("body")
    if not uploaded or not uploaded.filename or body not in ("colegiado", "nde"):
        flash("Informe o tipo e selecione uma portaria em PDF.", "danger")
        return redirect(url_for("admin.governance_management"))
    upload_dir = Path(current_app.root_path) / "static" / "docs" / "governance"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = uploaded.filename.replace("..", "_").replace("/", "_").replace("\\", "_")
    path = upload_dir / safe_name
    uploaded.save(path)
    try:
        doc, parsed = import_governance(path, body, title=request.form.get("title") or uploaded.filename, document_url=f"/static/docs/governance/{safe_name}")
        flash(f"Portaria importada: {doc.portaria_number}. {len(parsed['members'])} membro(s) extraído(s). Fotos do SUAP foram atualizadas quando disponíveis.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Não foi possível importar a portaria: {exc}", "danger")
    return redirect(url_for("admin.governance_management"))


@bp.post("/docentes/sincronizar-suap")
@admin_required
def sync_teacher_photos():
    from app.services.governance import sync_teacher_data_from_suap
    try:
        found, updated = sync_teacher_data_from_suap(Teacher.query.all())
        flash(f"SUAP sincronizado: {updated} docente(s) atualizado(s); {found} encontrado(s) no Campus ZN.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Não foi possível consultar os servidores do SUAP: {exc}", "danger")
    return redirect(url_for("admin.teachers"))


@bp.route("/conhecimento", methods=["GET", "POST"])
@admin_required
def knowledge_management():
    from app.services.knowledge import register_and_index
    if request.method == "POST":
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            flash("Selecione um arquivo PDF.", "danger")
            return redirect(url_for("admin.knowledge_management"))
        try:
            matrix_year = request.form.get("matrix_year", type=int)
            source, count = register_and_index(
                title=request.form["title"],
                document_type=request.form.get("document_type", "PPC"),
                matrix_year=matrix_year,
                description=request.form.get("description"),
                source_url=request.form.get("source_url"),
                file_storage=uploaded,
            )
            flash(f"Documento indexado com sucesso: {count} trechos.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Não foi possível indexar o documento: {exc}", "danger")
        return redirect(url_for("admin.knowledge_management"))
    q=request.args.get("q", "").strip(); query=KnowledgeSource.query.order_by(KnowledgeSource.created_at.desc());
    if q: query=query.filter(KnowledgeSource.title.ilike(f"%{q}%"))
    return render_template("admin/knowledge.html", sources=_paginate(query), q=q)


@bp.post("/conhecimento/<int:source_id>/excluir")
@admin_required
def delete_knowledge(source_id):
    from pathlib import Path
    from app.services.knowledge import knowledge_dir
    source = KnowledgeSource.query.get_or_404(source_id)
    path = knowledge_dir() / Path(source.filename).name
    db.session.delete(source)
    db.session.commit()
    try:
        path.unlink()
    except OSError:
        pass
    flash("Documento removido da base de conhecimento.", "success")
    return redirect(url_for("admin.knowledge_management"))


@bp.route("/projetos", methods=["GET", "POST"])
@admin_required
def projects():
    if request.method == "POST":
        project = Project(
            title=request.form["title"], acronym=request.form.get("acronym"),
            project_type=request.form["project_type"], description=request.form["description"],
            objectives=request.form.get("objectives"), coordinator=request.form.get("coordinator"),
            team=request.form.get("team"), period=request.form.get("period"),
            status=request.form.get("status", "Em andamento"), campus=request.form.get("campus") or "Natal-Zona Norte",
            academic_year=request.form.get("academic_year", type=int), funding=request.form.get("funding"),
            partners=request.form.get("partners"), url=request.form.get("url"), image_url=request.form.get("image_url"),
            is_pibid=bool(request.form.get("is_pibid")),
            has_licenciatura_students=(None if request.form.get("has_licenciatura_students") in (None, "") else request.form.get("has_licenciatura_students") == "true"),
            licenciatura_notes=request.form.get("licenciatura_notes"), featured=bool(request.form.get("featured")),
            published=bool(request.form.get("published")), source_system="manual",
        )
        db.session.add(project)
        db.session.commit()
        flash("Projeto cadastrado.", "success")
        return redirect(url_for("admin.projects"))
    q = request.args.get("q", "").strip()
    project_type = request.args.get("tipo", "").strip().lower()
    status = request.args.get("status", "").strip()
    licenciatura = request.args.get("licenciatura", "").strip().lower()
    source = request.args.get("source", "").strip().lower()
    query = Project.query.order_by(Project.project_type, Project.title)
    if q:
        from sqlalchemy import or_
        query = query.filter(or_(Project.title.ilike(f"%{q}%"), Project.coordinator.ilike(f"%{q}%"), Project.campus.ilike(f"%{q}%"), Project.description.ilike(f"%{q}%")))
    if project_type in ("pesquisa", "ensino", "extensao"):
        query = query.filter_by(project_type=project_type)
    if status:
        query = query.filter(Project.status.ilike(f"%{status}%"))
    if licenciatura == "sim":
        query = query.filter(Project.has_licenciatura_students.is_(True))
    elif licenciatura == "nao":
        query = query.filter(Project.has_licenciatura_students.is_(False))
    elif licenciatura == "pendente":
        query = query.filter(Project.has_licenciatura_students.is_(None))
    if source in ("suap", "manual"):
        query = query.filter_by(source_system=source)
    return render_template("admin/projects.html", projects=_paginate(query), q=q, project_type=project_type, status=status, licenciatura=licenciatura, source=source)


@bp.post("/projetos/<int:project_id>/excluir")
@admin_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Projeto excluído.", "success")
    return redirect(url_for("admin.projects"))


@bp.get("/enade")
@admin_required
def enade_management():
    exams = EnadeExam.query.order_by(EnadeExam.year.desc()).all()
    counts = {e.id: EnadeQuestion.query.filter_by(exam_id=e.id).count() for e in exams}
    return render_template("admin/enade.html", exams=exams, counts=counts)


@bp.post("/enade/<int:year>/importar")
@admin_required
def import_enade(year):
    from app.services.enade import import_exam_questions
    try:
        count, answers = import_exam_questions(year)
        flash(f"ENADE {year}: {count} questões objetivas importadas; {answers} gabaritos identificados.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Não foi possível importar o ENADE {year}: {exc}", "danger")
    return redirect(url_for("admin.enade_management"))
