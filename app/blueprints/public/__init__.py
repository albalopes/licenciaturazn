from flask import Blueprint, abort, render_template, request

from app.models import Discipline, Matrix, Project, SitePage, Teacher, TeacherHistory, GovernanceDocument, EnadeExam, EnadeQuestion, MemoriaWork, TeachingAssignment, AcademicEvent, AcademicPublication

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


@bp.get("/horarios")
def schedules():
    semester = request.args.get("semestre", "2026.2")
    assignments = TeachingAssignment.query.filter_by(semester=semester).order_by(TeachingAssignment.class_code, TeachingAssignment.start_time, TeachingAssignment.weekday, TeachingAssignment.course).all()
    weekdays = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
    classes = {}
    for item in assignments:
        classes.setdefault(item.class_code, []).append(item)
    # Cada turma passa a ser uma grade semanal: dias nas colunas e horários nas linhas.
    class_grids = {}
    for class_code, items in classes.items():
        slots = {}
        for item in items:
            key = (item.start_time, item.end_time)
            slots.setdefault(key, {day: [] for day in weekdays})
            if item.weekday in slots[key]:
                # Uma disciplina pode ocupar mais de um dia; cada ocorrência permanece
                # no seu dia, sem criar uma nova disciplina no histórico do docente.
                slots[key][item.weekday].append(item)
        rows = [{"start": key[0], "end": key[1], "days": days} for key, days in sorted(slots.items())]
        class_grids[class_code] = rows
    semesters = [r[0] for r in TeachingAssignment.query.with_entities(TeachingAssignment.semester).distinct().order_by(TeachingAssignment.semester.desc()).all()]
    return render_template("public/schedules.html", semester=semester, semesters=semesters, classes=classes, class_grids=class_grids, weekdays=weekdays)


@bp.get("/docentes/<int:teacher_id>")
def teacher_detail(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    assignments = TeachingAssignment.query.filter_by(teacher_id=teacher.id).order_by(TeachingAssignment.semester.desc(), TeachingAssignment.course, TeachingAssignment.class_code, TeachingAssignment.weekday, TeachingAssignment.start_time).all()

    def consolidate(items):
        grouped = {}
        order = []
        for item in items:
            key = (item.semester, item.course, item.class_code, item.room)
            if key not in grouped:
                grouped[key] = {
                    "semester": item.semester, "course": item.course, "class_code": item.class_code,
                    "room": item.room, "meetings": []
                }
                order.append(key)
            meeting = {"weekday": item.weekday, "start_time": item.start_time, "end_time": item.end_time}
            if meeting not in grouped[key]["meetings"]:
                grouped[key]["meetings"].append(meeting)
        day_order = {d:i for i,d in enumerate(["Segunda","Terça","Quarta","Quinta","Sexta"])}
        for item in grouped.values():
            item["meetings"].sort(key=lambda m: (day_order.get(m["weekday"], 99), m["start_time"]))
        return [grouped[k] for k in order]


    current = consolidate([a for a in assignments if a.semester == "2026.2"])
    history = {}
    for sem in sorted({a.semester for a in assignments}, reverse=True):
        history[sem] = consolidate([a for a in assignments if a.semester == sem])
    return render_template("public/teacher_detail.html", teacher=teacher, current_assignments=current, teaching_history=history)


@bp.get("/pagina/<slug>")
def page(slug):
    page = SitePage.query.filter_by(slug=slug, published=True).first()
    if not page:
        abort(404)
    if slug == "tcc":
        works = MemoriaWork.query.filter_by(active=True).order_by(MemoriaWork.date.desc(), MemoriaWork.title).all()
        return render_template("public/tcc.html", page=page, active_ppc=request.args.get("ppc", "2026"), memoria_works=works)
    if slug == "atpa":
        return render_template("public/atpa.html", page=page, active_ppc=request.args.get("ppc", "2026"))
    return render_template("public/page.html", page=page)

@bp.get("/coordenacao")
def coordination():
    from app.models import CourseCoordinator
    history = CourseCoordinator.query.filter_by(active=True).order_by(CourseCoordinator.start_year.desc(), CourseCoordinator.name).all()
    current = history[0] if history and history[0].end_year is None else None
    return render_template("public/coordination.html", history=history, current=current)


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


@bp.get("/eventos")
def events():
    from sqlalchemy import or_
    year = request.args.get("ano", type=int)
    theme = request.args.get("tema", "").strip()
    event = request.args.get("evento", "").strip()
    author = request.args.get("autor", "").strip()
    teacher = request.args.get("docente", "").strip()

    query = AcademicPublication.query.filter_by(published=True)
    if year:
        query = query.filter_by(year=year)
    if theme:
        query = query.filter(AcademicPublication.themes.ilike(f"%{theme}%"))
    if event:
        query = query.filter(AcademicPublication.event.ilike(f"%{event}%"))
    if author:
        query = query.filter(or_(AcademicPublication.authors.ilike(f"%{author}%"), AcademicPublication.student_authors.ilike(f"%{author}%"), AcademicPublication.teacher_authors.ilike(f"%{author}%")))
    if teacher:
        query = query.filter(AcademicPublication.teacher_authors.ilike(f"%{teacher}%"))
    publications = query.order_by(AcademicPublication.year.desc(), AcademicPublication.title).all()

    academic_events = AcademicEvent.query.filter_by(published=True).order_by(AcademicEvent.starts_at.desc()).all()
    years = [r[0] for r in AcademicPublication.query.with_entities(AcademicPublication.year).filter_by(published=True).distinct().order_by(AcademicPublication.year.desc()).all()]
    themes = sorted({theme.strip() for item in AcademicPublication.query.filter_by(published=True).all() for theme in (item.themes or '').split(';') if theme.strip()})
    event_names = sorted({item.event for item in AcademicPublication.query.filter_by(published=True).all() if item.event})
    teacher_names = sorted({name.strip() for item in AcademicPublication.query.filter_by(published=True).all() for name in (item.teacher_authors or "").split(";") if name.strip()})
    return render_template("public/events.html", publications=publications, academic_events=academic_events, years=years, themes=themes, event_names=event_names, teacher_names=teacher_names, selected_year=year, selected_theme=theme, selected_event=event, selected_author=author, selected_teacher=teacher)


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


@bp.get("/enade")
def enade():
    exams = EnadeExam.query.filter_by(active=True).order_by(EnadeExam.year.desc()).all()
    total_questions = {exam.id: EnadeQuestion.query.filter_by(exam_id=exam.id, active=True).count() for exam in exams}
    return render_template("public/enade.html", exams=exams, total_questions=total_questions)
