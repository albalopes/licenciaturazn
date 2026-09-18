from datetime import datetime
from app.extensions import db

class GovernanceDocument(db.Model):
    __tablename__ = 'governance_documents'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(40), nullable=False, index=True)  # colegiado | nde
    title = db.Column(db.String(220), nullable=False)
    portaria_number = db.Column(db.String(120), nullable=False)
    issued_at = db.Column(db.Date)
    semester = db.Column(db.String(20), index=True)
    document_url = db.Column(db.String(500))
    file_path = db.Column(db.String(500))
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    members = db.relationship('GovernanceMember', back_populates='document', cascade='all, delete-orphan')

class TeacherHistory(db.Model):
    __tablename__ = 'teacher_history'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    semester = db.Column(db.String(20), nullable=False, index=True)
    body = db.Column(db.String(40), nullable=False, index=True)  # colegiado | nde
    role = db.Column(db.String(120))
    governance_document_id = db.Column(db.Integer, db.ForeignKey('governance_documents.id'))
    active_in_term = db.Column(db.Boolean, default=True, nullable=False)
    teacher = db.relationship('Teacher', backref=db.backref('course_history', lazy='dynamic'))
    document = db.relationship('GovernanceDocument')
