from datetime import datetime

from flask_login import UserMixin

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    suap_id = db.Column(db.String(80), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    email = db.Column(db.String(180))
    registration = db.Column(db.String(50))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def admin_label(self):
        return "Administrador" if self.is_admin else "Usuário"


class Matrix(db.Model):
    __tablename__ = "matrices"
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(40), default="historica", nullable=False)
    document_url = db.Column(db.String(500))
    duration_semesters = db.Column(db.Integer, default=8)
    total_hours = db.Column(db.Integer)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    disciplines = db.relationship("Discipline", back_populates="matrix", cascade="all, delete-orphan", lazy=True)


class Discipline(db.Model):
    __tablename__ = "disciplines"
    id = db.Column(db.Integer, primary_key=True)
    matrix_id = db.Column(db.Integer, db.ForeignKey("matrices.id"), nullable=False, index=True)
    code = db.Column(db.String(40))
    name = db.Column(db.String(180), nullable=False)
    semester = db.Column(db.Integer)
    area = db.Column(db.String(120))
    kind = db.Column(db.String(40), default="obrigatoria")
    credits = db.Column(db.Integer)
    hours = db.Column(db.Integer)
    lesson_hours = db.Column(db.Integer)
    summary = db.Column(db.Text)
    objectives = db.Column(db.Text)
    contents = db.Column(db.Text)
    methodology = db.Column(db.Text)
    assessment = db.Column(db.Text)
    bibliography_basic = db.Column(db.Text)
    bibliography_complementary = db.Column(db.Text)
    support_software = db.Column(db.Text)
    matrix = db.relationship("Matrix", back_populates="disciplines")
    prerequisites = db.relationship(
        "DisciplinePrerequisite",
        foreign_keys="DisciplinePrerequisite.discipline_id",
        cascade="all, delete-orphan",
        back_populates="discipline",
    )


class DisciplinePrerequisite(db.Model):
    __tablename__ = "discipline_prerequisites"
    discipline_id = db.Column(db.Integer, db.ForeignKey("disciplines.id"), primary_key=True)
    prerequisite_id = db.Column(db.Integer, db.ForeignKey("disciplines.id"), primary_key=True)
    discipline = db.relationship("Discipline", foreign_keys=[discipline_id], back_populates="prerequisites")
    prerequisite = db.relationship("Discipline", foreign_keys=[prerequisite_id])


class Teacher(db.Model):
    __tablename__ = "teachers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    photo_url = db.Column(db.String(500))
    email = db.Column(db.String(180))
    lattes_url = db.Column(db.String(500))
    orcid_url = db.Column(db.String(500))
    education = db.Column(db.Text)
    areas = db.Column(db.Text)
    bio = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)


class SitePage(db.Model):
    __tablename__ = "site_pages"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80))
    content = db.Column(db.Text)
    published = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(500), nullable=False)
    published = db.Column(db.Boolean, default=True, nullable=False)
    published_at = db.Column(db.DateTime, default=datetime.utcnow)


class AcademicEvent(db.Model):
    __tablename__ = "academic_events"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime)
    category = db.Column(db.String(80))
    url = db.Column(db.String(500))
    published = db.Column(db.Boolean, default=True, nullable=False)


class GovernanceMember(db.Model):
    __tablename__ = "governance_members"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(40), nullable=False)  # colegiado | nde
    name = db.Column(db.String(180), nullable=False)
    role = db.Column(db.String(120))
    term = db.Column(db.String(80))
    document_url = db.Column(db.String(500))
    active = db.Column(db.Boolean, default=True, nullable=False)


class EntranceSchedule(db.Model):
    __tablename__ = "entrance_schedule"
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)
    shift = db.Column(db.String(40), nullable=False)
    matrix_year = db.Column(db.Integer)
    notes = db.Column(db.Text)
    published = db.Column(db.Boolean, default=True, nullable=False)


class FAQ(db.Model):
    __tablename__ = "faqs"
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(300), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80))
    position = db.Column(db.Integer, default=0)
    published = db.Column(db.Boolean, default=True, nullable=False)


from .knowledge import KnowledgeChunk, KnowledgeSource
from .project import Project
