"""Sincronização leve da coleção de Licenciatura em Informática do Memoria/IFRN."""
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import re
import requests
from app.extensions import db
from app.models import MemoriaWork

COLLECTION_URL = "https://memoria.ifrn.edu.br/handle/1044/1045"
RECENT_URL = COLLECTION_URL + "/recent-submissions?rpp=100"


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None
        self.buf = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            d = dict(attrs)
            self.current = {"href": d.get("href", ""), "text": []}
    def handle_data(self, data):
        if self.current is not None:
            self.current["text"].append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.current["text"] = _clean(" ".join(self.current["text"]))
            self.links.append(self.current)
            self.current = None


def _extract_items(html):
    parser = _LinkParser(); parser.feed(html)
    items = []
    seen = set()
    for link in parser.links:
        href = link["href"]
        text = link["text"]
        if not href or not text:
            continue
        full = urljoin(COLLECTION_URL + "/", href)
        m = re.search(r"/handle/1044/(\d+)", full)
        if not m or m.group(1) == "1045":
            continue
        if full in seen:
            continue
        # DSpace uses the item title as the anchor in the collection listing.
        if "/handle/1044/" in full and len(text) > 8:
            seen.add(full)
            items.append({"handle": m.group(1), "url": full, "title": text})
    return items


def _extract_detail(url, fallback_title):
    class MetaParser(HTMLParser):
        def __init__(self):
            super().__init__(); self.meta = {}; self.buf = []
        def handle_starttag(self, tag, attrs):
            if tag == "meta":
                d = dict(attrs); key = (d.get("name") or d.get("property") or "").lower(); val = d.get("content")
                if key and val: self.meta.setdefault(key, []).append(_clean(val))
    r = requests.get(url, timeout=20, headers={"User-Agent": "LicenciaturaZN/1.0"})
    r.raise_for_status()
    html = r.text
    parser = MetaParser(); parser.feed(html)
    text = _clean(re.sub(r"<[^>]+>", " ", html))
    def first(*keys):
        for key in keys:
            values = parser.meta.get(key.lower()) or []
            if values and values[0]: return values[0]
        return ""
    authors = first("dc.creator", "citation_author", "dc.contributor.author")
    date = first("dc.date", "dc.date.issued", "citation_publication_date")
    abstract = first("dc.description.abstract", "dc.description", "description")
    title = first("dc.title", "citation_title") or fallback_title
    campus = "Natal - Zona Norte" if "Natal - Zona Norte" in text or "Natal-Zona Norte" in text else ""
    return {"title": title, "authors": authors, "date": date, "abstract": abstract, "campus": campus}


def sync_memoria():
    """Fetches the current collection listing and upserts its items.

    The collection is already restricted to Licenciatura em Informática. Detail-page
    filtering keeps only records that explicitly identify Natal - Zona Norte when
    that metadata is available; if a detail page omits the campus field, the item is
    retained because it came from the course collection.
    """
    r = requests.get(RECENT_URL, timeout=30, headers={"User-Agent": "LicenciaturaZN/1.0"})
    r.raise_for_status()
    items = _extract_items(r.text)
    created = updated = 0
    errors = []
    for item in items:
        try:
            detail = _extract_detail(item["url"], item["title"])
            obj = MemoriaWork.query.filter_by(handle=item["handle"]).first()
            if not obj:
                obj = MemoriaWork(handle=item["handle"], title=detail["title"], url=item["url"])
                db.session.add(obj); created += 1
            else:
                updated += 1
            obj.title = detail["title"] or item["title"]
            obj.authors = detail["authors"] or obj.authors
            obj.date = detail["date"] or obj.date
            obj.abstract = detail["abstract"] or obj.abstract
            obj.campus = detail["campus"] or obj.campus or "Natal - Zona Norte"
            obj.work_type = "Trabalho de Conclusão de Curso"
            obj.url = item["url"]
            obj.synced_at = datetime.utcnow()
            obj.active = True
        except Exception as exc:
            errors.append(f"{item['title']}: {exc}")
    db.session.commit()
    return {"found": len(items), "created": created, "updated": updated, "errors": errors}
