from flask import Blueprint, abort, render_template, request

from app.models import Discipline, Matrix, Project, SitePage, Teacher, TeacherHistory, GovernanceDocument

bp = Blueprint("public", __name__)


@bp.get("/")
def home():
    matrices = Matrix.query.filter_by(is_published=True).order_by(Matrix.year.desc()).all()
    teachers = Teacher.query.filter_by(active=True).order_by(Teacher.name).all()
    return render_template("public/home.html", matrices=matrices, teachers=teachers)


@bp.get("/matrizes")
def matrices():
    return render_template("public/matrices.html", matrices=Matrix.query.order_by(Matrix.year.desc()).all())


@bp.get("/matrizes/<int:year>")
def matrix_detail(year):
    matrix = Matrix.query.filter_by(year=year, is_published=True).first_or_404()
    semester = request.args.get("semestre", type=int)
    kind = request.args.get("tipo")
    area = request.args.get("area")
    query = request.args.get("q", "").strip()
    disciplines = Discipline.query.filter_by(matrix_id=matrix.id)
    if semester:
        disciplines = disciplines.filter_by(semester=semester)
    if kind:
        disciplines = disciplines.filter_by(kind=kind)
    if area:
        disciplines = disciplines.filter_by(area=area)
    if query:
        disciplines = disciplines.filter(Discipline.name.ilike(f"%{query}%"))
    disciplines = disciplines.order_by(Discipline.semester, Discipline.name).all()
    areas = [r[0] for r in Discipline.query.with_entities(Discipline.area).filter_by(matrix_id=matrix.id).distinct().order_by(Discipline.area).all() if r[0]]
    return render_template("public/matrix_detail.html", matrix=matrix, disciplines=disciplines, areas=areas)


@bp.get("/disciplinas/<int:discipline_id>")
def discipline_detail(discipline_id):
    discipline = Discipline.query.get_or_404(discipline_id)
    return render_template("public/discipline_detail.html", discipline=discipline)


@bp.get("/docentes")
def teachers():
    teachers = Teacher.query.filter_by(active=True).order_by(Teacher.name).all()
    history = TeacherHistory.query.order_by(TeacherHistory.semester.desc(), TeacherHistory.body, TeacherHistory.role, TeacherHistory.teacher_id).all()
    return render_template("public/teachers.html", teachers=teachers, history=history)


@bp.get("/docentes/<int:teacher_id>")
def teacher_detail(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    return render_template("public/teacher_detail.html", teacher=teacher)


@bp.get("/pagina/<slug>")
def page(slug):
    page = SitePage.query.filter_by(slug=slug, published=True).first()
    if not page:
        abort(404)
    return render_template("public/page.html", page=page)

@bp.get("/gestao/<body>")
def governance(body):
    from app.models import GovernanceMember
    if body not in ("colegiado", "nde"):
        abort(404)
    current_doc = GovernanceDocument.query.filter_by(body=body, active=True).order_by(GovernanceDocument.issued_at.desc()).first()
    members_query = GovernanceMember.query.filter_by(body=body, active=True)
    if current_doc:
        members_query = members_query.filter_by(governance_document_id=current_doc.id)
    members = members_query.order_by(GovernanceMember.role, GovernanceMember.name).all()
    history = GovernanceDocument.query.filter_by(body=body).order_by(GovernanceDocument.issued_at.desc()).all()
    title = "Colegiado do curso" if body == "colegiado" else "Núcleo Docente Estruturante"
    return render_template("public/governance.html", members=members, history=history, current_doc=current_doc, title=title, body=body)


@bp.get("/ingressos")
def entrances():
    from app.models import EntranceSchedule
    return render_template("public/entrances.html", entries=EntranceSchedule.query.filter_by(published=True).order_by(EntranceSchedule.year.desc()).all())


@bp.get("/documentos")
def documents():
    from app.models import Document
    return render_template("public/documents.html", documents=Document.query.filter_by(published=True).order_by(Document.category, Document.title).all())


@bp.get("/faq")
def faq():
    from app.models import FAQ
    return render_template("public/faq.html", faqs=FAQ.query.filter_by(published=True).order_by(FAQ.category, FAQ.position, FAQ.question).all())


@bp.get("/projetos")
def projects():
    project_type = request.args.get("tipo", "").strip().lower()
    query = Project.query.filter_by(published=True)
    if project_type in ("pesquisa", "ensino", "extensao"):
        query = query.filter_by(project_type=project_type)
    projects = query.order_by(Project.featured.desc(), Project.project_type, Project.title).all()
    return render_template("public/projects.html", projects=projects, selected_type=project_type)


@bp.get("/projetos/<int:project_id>")
def project_detail(project_id):
    project = Project.query.filter_by(id=project_id, published=True).first_or_404()
    return render_template("public/project_detail.html", project=project)


@bp.get("/pibid")
def pibid():
    projects = Project.query.filter_by(published=True, is_pibid=True).order_by(Project.featured.desc(), Project.title).all()
    return render_template("public/pibid.html", projects=projects)
