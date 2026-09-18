from datetime import datetime
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import KnowledgeChunk, KnowledgeSource
from app.services.chatbot import _embed
from app.services.document_processor import extract_pdf_pages, safe_filename, split_pages


def knowledge_dir():
    configured = current_app.config.get("KNOWLEDGE_UPLOAD_DIR", "knowledge_documents")
    path = Path(configured)
    if not path.is_absolute():
        path = Path(current_app.instance_path) / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def index_source(source: KnowledgeSource):
    path = Path(source.filename)
    if not path.is_absolute():
        path = knowledge_dir() / path.name
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    pages = extract_pdf_pages(str(path))
    chunks = split_pages(pages)

    source.chunks.clear()
    db.session.flush()
    for index, item in enumerate(chunks):
        embedding = None
        if current_app.config.get("OPENAI_API_KEY"):
            try:
                embedding = _embed(item["content"])
            except Exception:
                current_app.logger.exception("Não foi possível gerar embedding do trecho %s", index)
        db.session.add(KnowledgeChunk(
            source=source,
            chunk_index=index,
            page=item["page"],
            content=item["content"],
            embedding=embedding,
        ))
    source.chunk_count = len(chunks)
    source.indexed_at = datetime.utcnow()
    db.session.commit()
    return len(chunks)


def save_uploaded_pdf(file_storage):
    filename = safe_filename(file_storage.filename or "documento.pdf")
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Apenas arquivos PDF são aceitos.")
    target = knowledge_dir() / filename
    file_storage.save(target)
    return target


def register_and_index(title, document_type, matrix_year, description, source_url, file_storage):
    target = save_uploaded_pdf(file_storage)
    source = KnowledgeSource(
        title=title,
        document_type=document_type,
        matrix_year=matrix_year,
        description=description,
        filename=target.name,
        source_url=source_url,
        active=True,
    )
    db.session.add(source)
    db.session.commit()
    try:
        count = index_source(source)
    except Exception:
        db.session.delete(source)
        db.session.commit()
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return source, count
