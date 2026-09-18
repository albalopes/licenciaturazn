import re
from pathlib import Path

from pypdf import PdfReader


def extract_pdf_pages(path: str):
    reader = PdfReader(path)
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if text:
            pages.append((number, text))
    return pages


def split_pages(pages, chunk_size=2600, overlap=350):
    chunks = []
    for page_number, text in pages:
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                cut = text.rfind("\n", start, end)
                if cut < start + int(chunk_size * 0.55):
                    cut = text.rfind(". ", start, end)
                if cut >= start + int(chunk_size * 0.55):
                    end = cut + (1 if text[cut:cut + 2] == ". " else 0)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append({"page": page_number, "content": chunk})
            if end >= len(text):
                break
            start = max(0, end - overlap)
    return chunks


def safe_filename(filename):
    filename = Path(filename).name
    filename = re.sub(r"[^\w.\-]+", "_", filename, flags=re.UNICODE)
    return filename[:220] or "documento.pdf"
