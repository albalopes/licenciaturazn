from datetime import datetime

from app.extensions import db


class KnowledgeSource(db.Model):
    __tablename__ = "knowledge_sources"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    document_type = db.Column(db.String(60), nullable=False, default="PPC")
    matrix_year = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text)
    filename = db.Column(db.String(300), nullable=False)
    source_url = db.Column(db.String(700))
    active = db.Column(db.Boolean, default=True, nullable=False)
    indexed_at = db.Column(db.DateTime)
    chunk_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    chunks = db.relationship(
        "KnowledgeChunk",
        back_populates="source",
        cascade="all, delete-orphan",
        lazy=True,
    )


class KnowledgeChunk(db.Model):
    __tablename__ = "knowledge_chunks"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("knowledge_sources.id"), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    page = db.Column(db.Integer)
    heading = db.Column(db.String(300))
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.JSON)

    source = db.relationship("KnowledgeSource", back_populates="chunks")
