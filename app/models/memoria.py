from datetime import datetime
from app.extensions import db


class MemoriaWork(db.Model):
    __tablename__ = "memoria_works"
    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    authors = db.Column(db.Text)
    date = db.Column(db.String(40))
    abstract = db.Column(db.Text)
    url = db.Column(db.String(700), nullable=False)
    campus = db.Column(db.String(180))
    work_type = db.Column(db.String(120), default="Trabalho de Conclusão de Curso")
    synced_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    published_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=False, nullable=False)
    accepted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    accepted_at = db.Column(db.DateTime)
    excluded = db.Column(db.Boolean, default=False, nullable=False, index=True)
