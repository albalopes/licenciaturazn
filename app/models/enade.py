from datetime import datetime
from app.extensions import db


class EnadeExam(db.Model):
    __tablename__ = "enade_exams"
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True, index=True)
    area = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(220), nullable=False)
    exam_url = db.Column(db.String(500), nullable=False)
    answer_key_url = db.Column(db.String(500))
    source_url = db.Column(db.String(500))
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)
    imported_at = db.Column(db.DateTime)
    questions = db.relationship("EnadeQuestion", back_populates="exam", cascade="all, delete-orphan")


class EnadeQuestion(db.Model):
    __tablename__ = "enade_questions"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("enade_exams.id"), nullable=False, index=True)
    number = db.Column(db.Integer, nullable=False)
    component = db.Column(db.String(80))
    statement = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=False)
    correct_option = db.Column(db.String(1))
    source_page = db.Column(db.Integer)
    source_url = db.Column(db.String(500))
    active = db.Column(db.Boolean, default=True, nullable=False)
    exam = db.relationship("EnadeExam", back_populates="questions")
    attempts = db.relationship("EnadeAttempt", back_populates="question", cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("exam_id", "number", name="uq_enade_exam_question"),)


class EnadeAttempt(db.Model):
    __tablename__ = "enade_attempts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("enade_questions.id"), nullable=False, index=True)
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    score = db.Column(db.Float, nullable=False, default=0)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("enade_attempts", lazy="dynamic"))
    question = db.relationship("EnadeQuestion", back_populates="attempts")
    __table_args__ = (db.UniqueConstraint("user_id", "question_id", name="uq_enade_user_question"),)
