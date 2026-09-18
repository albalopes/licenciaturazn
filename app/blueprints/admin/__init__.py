from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AcademicEvent, Discipline, Document, Matrix, Project, SitePage, Teacher, KnowledgeSource

bp = Blueprint("admin", __name__)


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


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
    return render_template("admin/matrices.html", matrices=Matrix.query.order_by(Matrix.year.desc()).all())


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
    return render_template("admin/disciplines.html", disciplines=Discipline.query.order_by(Discipline.matrix_id, Discipline.semester, Discipline.name).all(), matrices=Matrix.query.order_by(Matrix.year.desc()).all())


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
            name=request.form["name"], photo_url=request.form.get("photo_url"), email=request.form.get("email"),
            lattes_url=request.form.get("lattes_url"), orcid_url=request.form.get("orcid_url"), education=request.form.get("education"),
            areas=request.form.get("areas"), bio=request.form.get("bio"), active=bool(request.form.get("active")),
        )
        db.session.add(teacher)
        db.session.commit()
        flash("Docente cadastrado.", "success")
        return redirect(url_for("admin.teachers"))
    return render_template("admin/teachers.html", teachers=Teacher.query.order_by(Teacher.name).all())


@bp.route("/paginas", methods=["GET", "POST"])
@admin_required
def pages():
    if request.method == "POST":
        page = SitePage(slug=request.form["slug"], title=request.form["title"], category=request.form.get("category"), content=request.form.get("content"), published=bool(request.form.get("published")))
        db.session.add(page)
        db.session.commit()
        flash("Página criada.", "success")
        return redirect(url_for("admin.pages"))
    return render_template("admin/pages.html", pages=SitePage.query.order_by(SitePage.title).all())


@bp.route("/documentos", methods=["GET", "POST"])
@admin_required
def documents():
    if request.method == "POST":
        document = Document(title=request.form["title"], category=request.form["category"], description=request.form.get("description"), url=request.form["url"], published=bool(request.form.get("published")))
        db.session.add(document)
        db.session.commit()
        flash("Documento cadastrado.", "success")
        return redirect(url_for("admin.documents"))
    return render_template("admin/documents.html", documents=Document.query.order_by(Document.published_at.desc()).all())


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
    return render_template("admin/events.html", events=AcademicEvent.query.order_by(AcademicEvent.starts_at.desc()).all())

@bp.route("/gestao", methods=["GET", "POST"])
@admin_required
def governance_management():
    from app.models import GovernanceMember
    if request.method == "POST":
        member = GovernanceMember(body=request.form["body"], name=request.form["name"], role=request.form.get("role"), term=request.form.get("term"), document_url=request.form.get("document_url"), active=bool(request.form.get("active")))
        db.session.add(member)
        db.session.commit()
        flash("Membro cadastrado.", "success")
        return redirect(url_for("admin.governance_management"))
    return render_template("admin/governance.html", members=GovernanceMember.query.order_by(GovernanceMember.body, GovernanceMember.name).all())


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
    return render_template("admin/entrances.html", entries=EntranceSchedule.query.order_by(EntranceSchedule.year.desc()).all())


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
    return render_template("admin/faq.html", faqs=FAQ.query.order_by(FAQ.category, FAQ.position).all())


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
    return render_template("admin/knowledge.html", sources=KnowledgeSource.query.order_by(KnowledgeSource.created_at.desc()).all())


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
            title=request.form["title"],
            acronym=request.form.get("acronym"),
            project_type=request.form["project_type"],
            description=request.form["description"],
            objectives=request.form.get("objectives"),
            coordinator=request.form.get("coordinator"),
            team=request.form.get("team"),
            period=request.form.get("period"),
            status=request.form.get("status", "Em andamento"),
            funding=request.form.get("funding"),
            partners=request.form.get("partners"),
            url=request.form.get("url"),
            image_url=request.form.get("image_url"),
            is_pibid=bool(request.form.get("is_pibid")),
            featured=bool(request.form.get("featured")),
            published=bool(request.form.get("published")),
        )
        db.session.add(project)
        db.session.commit()
        flash("Projeto cadastrado.", "success")
        return redirect(url_for("admin.projects"))
    return render_template("admin/projects.html", projects=Project.query.order_by(Project.project_type, Project.title).all())


@bp.post("/projetos/<int:project_id>/excluir")
@admin_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Projeto excluído.", "success")
    return redirect(url_for("admin.projects"))
