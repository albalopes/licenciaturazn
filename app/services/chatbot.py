import math
import re
from typing import Optional

import requests
from flask import current_app

from app.models import KnowledgeChunk, KnowledgeSource


def _normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\sÀ-ÿ]", " ", text, flags=re.UNICODE)
    return [token for token in text.split() if len(token) > 2]


def _lexical_score(question, content):
    q = set(_normalize(question))
    c = _normalize(content)
    if not q or not c:
        return 0.0
    counts = {token: c.count(token) for token in q}
    matched = sum(1 for token, count in counts.items() if count)
    frequency = sum(min(count, 3) for count in counts.values())
    return (matched / len(q)) * 0.75 + min(frequency / max(len(q), 1), 1.0) * 0.25


def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _openai_headers():
    return {
        "Authorization": f"Bearer {current_app.config['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }


def _embed(text):
    key = current_app.config.get("OPENAI_API_KEY")
    if not key:
        return None
    url = current_app.config["OPENAI_BASE_URL"].rstrip("/") + "/embeddings"
    payload = {"model": current_app.config["OPENAI_EMBEDDING_MODEL"], "input": text}
    response = requests.post(url, headers=_openai_headers(), json=payload, timeout=45)
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["embedding"]


def _retrieve(question, matrix_year=None, limit=6):
    query = KnowledgeChunk.query.join(KnowledgeSource).filter(KnowledgeSource.active.is_(True))
    if matrix_year:
        scoped = query.filter(
            (KnowledgeSource.matrix_year == matrix_year) | (KnowledgeSource.matrix_year.is_(None))
        )
        chunks = scoped.all()
        if not chunks:
            chunks = query.all()
    else:
        chunks = query.all()

    if not chunks:
        return []

    q_embedding = None
    if current_app.config.get("OPENAI_API_KEY"):
        try:
            q_embedding = _embed(question)
        except Exception:
            q_embedding = None

    ranked = []
    for chunk in chunks:
        lexical = _lexical_score(question, chunk.content)
        semantic = _cosine(q_embedding, chunk.embedding) if q_embedding and chunk.embedding else 0.0
        score = semantic * 0.82 + lexical * 0.18 if q_embedding and chunk.embedding else lexical
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [chunk for score, chunk in ranked[:limit] if score > 0]


def _format_sources(chunks):
    sources = []
    seen = set()
    for chunk in chunks:
        key = (chunk.source_id, chunk.page)
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "title": chunk.source.title,
            "type": chunk.source.document_type,
            "matrix_year": chunk.source.matrix_year,
            "page": chunk.page,
            "url": chunk.source.source_url,
        })
    return sources


def _response_text(data):
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()
    texts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("text"):
                texts.append(content["text"])
    return "\n".join(texts).strip()


def _generate_with_openai(question, chunks):
    context_parts = []
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.source
        label = f"[Fonte {index}: {source.title}, página {chunk.page or '?'}]"
        context_parts.append(f"{label}\n{chunk.content}")
    context = "\n\n---\n\n".join(context_parts)

    system = (
        "Você é o Assistente da Licenciatura em Informática do IFRN Campus Natal-Zona Norte. "
        "Responda em português do Brasil. Use somente as fontes fornecidas no contexto. "
        "Não invente regras, prazos, cargas horárias ou decisões administrativas. "
        "Quando as fontes não forem suficientes, diga explicitamente que a informação não foi localizada "
        "e oriente o estudante a procurar a Coordenação do Curso. "
        "Diferencie regras gerais da Organização Didática de regras específicas de um PPC/matriz. "
        "Ao final, indique as fontes utilizadas com o título e a página quando disponível."
    )
    user = f"Pergunta do estudante:\n{question}\n\nContexto documental:\n{context}"
    url = current_app.config["OPENAI_BASE_URL"].rstrip("/") + "/responses"
    payload = {
        "model": current_app.config["OPENAI_MODEL"],
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": user}]},
        ],
    }
    response = requests.post(url, headers=_openai_headers(), json=payload, timeout=90)
    response.raise_for_status()
    text = _response_text(response.json())
    if not text:
        raise RuntimeError("A API de IA não retornou texto.")
    return text


def answer_question(question: str, matrix_year: Optional[int] = None):
    chunks = _retrieve(question, matrix_year=matrix_year)
    sources = _format_sources(chunks)

    if not chunks:
        return {
            "answer": "Não encontrei trechos relevantes na base documental do portal. Cadastre e indexe o PPC ou a Organização Didática correspondente, ou procure a Coordenação do Curso.",
            "sources": [],
            "mode": "retrieval-only",
        }

    if current_app.config.get("OPENAI_API_KEY"):
        try:
            answer = _generate_with_openai(question, chunks)
            return {"answer": answer, "sources": sources, "mode": "rag"}
        except Exception as exc:
            current_app.logger.exception("Falha na geração do chatbot: %s", exc)

    excerpts = []
    for chunk in chunks[:3]:
        excerpts.append(
            f"**{chunk.source.title} — p. {chunk.page or '?'}**\n{chunk.content[:900].strip()}"
        )
    return {
        "answer": (
            "O portal encontrou estes trechos relevantes nos documentos, mas a geração por IA está desativada ou indisponível. "
            "Configure OPENAI_API_KEY para transformar a recuperação em respostas conversacionais.\n\n" + "\n\n".join(excerpts)
        ),
        "sources": sources,
        "mode": "retrieval-only",
    }
