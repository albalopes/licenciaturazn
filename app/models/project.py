from datetime import datetime
from app.extensions import db

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    suap_id = db.Column(db.String(80), index=True)
    source_system = db.Column(db.String(40), default='manual', nullable=False)
    title = db.Column(db.String(220), nullable=False)
    acronym = db.Column(db.String(60))
    project_type = db.Column(db.String(30), nullable=False, index=True)  # pesquisa | ensino | extensão
    description = db.Column(db.Text, nullable=False)
    objectives = db.Column(db.Text)
    coordinator = db.Column(db.String(180))
    team = db.Column(db.Text)
    period = db.Column(db.String(80))
    status = db.Column(db.String(60), default='Em andamento', index=True)
    campus = db.Column(db.String(120), index=True)
    academic_year = db.Column(db.Integer, index=True)
    funding = db.Column(db.String(180))
    partners = db.Column(db.Text)
    url = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    is_pibid = db.Column(db.Boolean, default=False, nullable=False, index=True)
    has_licenciatura_students = db.Column(db.Boolean, nullable=True, index=True)
    licenciatura_notes = db.Column(db.Text)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    published = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
