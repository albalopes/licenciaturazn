import json
import re
from datetime import datetime
from io import BytesIO

import requests
from pypdf import PdfReader

from app.extensions import db
from app.models import EnadeExam, EnadeQuestion

EXAMS = [
    {
        "year": 2017,
        "area": "Ciência da Computação — Licenciatura",
        "title": "ENADE 2017 — Ciência da Computação (Licenciatura)",
        "exam_url": "https://download.inep.gov.br/educacao_superior/enade/provas/2017/04_CIE_COM_LICENCIATURA_BAIXA.pdf",
        "answer_key_url": "https://download.inep.gov.br/educacao_superior/enade/gabaritos/2017/04_CIE_COM_LICENCIATURA_GABARITO.pdf",
        "source_url": "https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enade/provas-e-gabaritos",
    },
    {
        "year": 2021,
        "area": "Ciência da Computação — Licenciatura",
        "title": "ENADE 2021 — Ciência da Computação (Licenciatura)",
        "exam_url": "https://download.inep.gov.br/enade/provas_e_gabaritos/2021_PV_licenciatura_ciencia_computacao.pdf",
        "answer_key_url": "https://download.inep.gov.br/enade/provas_e_gabaritos/2021_GB_licenciatura_ciencia_computacao.pdf",
        "source_url": "https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enade/provas-e-gabaritos/2021",
    },
    {
        "year": 2024,
        "area": "Computação — Licenciatura",
        "title": "ENADE 2024 — Computação (Licenciatura)",
        "exam_url": "https://download.inep.gov.br/enade/provas_e_gabaritos/2024_Computacao_PV_1.pdf",
        "answer_key_url": "https://download.inep.gov.br/enade/provas_e_gabaritos/2024_MP_ciencias_da_computacao.pdf",
        "source_url": "https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enade-das-licenciaturas/provas-e-gabaritos/2024",
        "notes": "A edição 2024 utilizou 10 cadernos e a metodologia BIB. Este registro usa o caderno 1 como referência para o banco local.",
    },
]


def seed_exams():
    for data in EXAMS:
        exam = EnadeExam.query.filter_by(year=data["year"]).first()
        if not exam:
            exam = EnadeExam(year=data["year"])
            db.session.add(exam)
        for key, value in data.items():
            if key != "year":
                setattr(exam, key, value)
    db.session.commit()


def _download(url):
    r = requests.get(url, timeout=60, headers={"User-Agent": "LicenciaturaZN/1.0"})
    r.raise_for_status()
    return r.content


def _pdf_text(content):
    reader = PdfReader(BytesIO(content))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        pages.append((i, page.extract_text() or ""))
    return pages


def _normalize(text):
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_questions(pages):
    # Works with the question labels used in the official ENADE PDFs.
    all_text = "\n\n".join(f"\n[[PAGE:{page}]]\n{text}" for page, text in pages)
    pattern = re.compile(r"(?im)(?:QUEST[ÃA]O|QUeSTÃo|QUESTÃO)\s+(\d{1,2})\s*(.*?)(?=(?:\n(?:QUEST[ÃA]O|QUeSTÃo|QUESTÃO)\s+\d{1,2}\b)|\Z)", re.S)
    found = []
    seen = set()
    for m in pattern.finditer(all_text):
        number = int(m.group(1))
        if number in seen or number > 100:
            continue
        block = _normalize(m.group(2))
        if not block or "PERCEPÇÃO" in block[:100].upper() or "GRAU DE DIFICULDADE" in block[:180].upper():
            continue
        page_match = re.search(r"\[\[PAGE:(\d+)\]\]", block)
        page = int(page_match.group(1)) if page_match else None
        block = re.sub(r"\[\[PAGE:\d+\]\]\s*", "", block)
        # Locate A-E alternatives. The statement is everything before the first option.
        opt_matches = list(re.finditer(r"(?:^|\n|\s)([A-E])\s+(?=[A-ZÁÀÃÂÉÊÍÓÔÕÚÜ0-9\"(])", block))
        options = {}
        statement = block
        if len(opt_matches) >= 4:
            first = opt_matches[0]
            statement = block[:first.start()].strip()
            for idx, om in enumerate(opt_matches):
                key = om.group(1)
                start = om.end()
                end = opt_matches[idx + 1].start() if idx + 1 < len(opt_matches) else len(block)
                options[key] = block[start:end].strip()
        if len(options) < 3:
            continue
        found.append({"number": number, "statement": statement, "options": options, "source_page": page})
        seen.add(number)
    return found


def _extract_answer_key(text_pages):
    text = _normalize("\n".join(t for _, t in text_pages))
    answers = {}
    for m in re.finditer(r"QUESTÃO\s+(\d{1,2})\s+([A-E])\b", text, re.I):
        answers.setdefault(int(m.group(1)), m.group(2).upper())
    # O Mapa de Prova 2024 usa tabela com colunas: item | gabarito | ...
    for m in re.finditer(r"\|\s*(\d{1,3})\s*\|\s*([A-E])\s*\|", text):
        answers.setdefault(int(m.group(1)), m.group(2).upper())
    return answers


def import_exam_questions(year):
    exam = EnadeExam.query.filter_by(year=year).first()
    if not exam:
        raise ValueError("Edição do ENADE não cadastrada.")
    pages = _pdf_text(_download(exam.exam_url))
    questions = _extract_questions(pages)
    answer_key = {}
    if exam.answer_key_url:
        try:
            answer_key = _extract_answer_key(_pdf_text(_download(exam.answer_key_url)))
        except Exception:
            answer_key = {}
    EnadeQuestion.query.filter_by(exam_id=exam.id).delete(synchronize_session=False)
    for item in questions:
        component = "Formação Geral" if (year < 2024 and item["number"] <= 8) else "Componente Específico"
        if year == 2024:
            component = "Formação Geral Docente" if item["number"] <= 27 else "Componente Específico"
        q = EnadeQuestion(
            exam_id=exam.id,
            number=item["number"],
            component=component,
            statement=item["statement"],
            options_json=json.dumps(item["options"], ensure_ascii=False),
            correct_option=answer_key.get(item["number"]),
            source_page=item.get("source_page"),
            source_url=exam.exam_url,
        )
        db.session.add(q)
    exam.imported_at = datetime.utcnow()
    db.session.commit()
    return len(questions), len(answer_key)
