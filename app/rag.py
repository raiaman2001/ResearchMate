"""F9: Local PDF RAG. PDF -> pages -> chunks -> Chroma ("docs"). Researcher ko `search_documents` tool milta hai."""
import hashlib
import io
import re

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app import config
from app.memory.vector import VectorStore


def chunk_text(text, size=None, overlap=None):
    """Sentence boundary ka dhyan rakhte hue ~size characters ke chunks (overlap ke saath)."""
    size, overlap = size or config.CHUNK_CHARS, overlap or config.CHUNK_OVERLAP
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = max(text.rfind(". ", start, end), text.rfind("। ", start, end))
            if cut > start + size // 2:
                end = cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def doc_url(name, page):
    return f"doc://{re.sub(r'[^A-Za-z0-9_.-]+', '_', name)}#p{page}"


class DocStore:
    def __init__(self, vector=None):
        self.vector = vector or VectorStore("docs")

    def ingest_pdf(self, data: bytes, filename: str):
        if len(data) > config.MAX_PDF_MB * 1024 * 1024:
            raise ValueError(f"PDF {config.MAX_PDF_MB} MB se badi hai.")
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("PDF password-protected hai.")
            pages = [(i, (p.extract_text() or "")) for i, p in enumerate(reader.pages, 1)]
        except PyPdfError as e:
            raise ValueError(f"PDF read nahi ho payi: {e}") from e

        doc_id = hashlib.sha1(data).hexdigest()[:10]
        if self.vector.get(where={"doc_id": doc_id}):
            return {"doc_id": doc_id, "name": filename, "pages": len(pages), "chunks": 0,
                    "skipped_pages": [], "duplicate": True}

        ids, docs, metas, skipped = [], [], [], []
        for page, text in pages:
            chunks = chunk_text(text)
            if not chunks:
                skipped.append(page)               # khali / scanned page (OCR nahi hai)
            for n, c in enumerate(chunks):
                ids.append(f"{doc_id}-p{page}-{n}")
                docs.append(c)
                metas.append({"doc_id": doc_id, "doc": filename, "page": page, "url": doc_url(filename, page)})
        if not ids:
            raise ValueError("PDF me text nahi mila (shayad scanned images hain; OCR supported nahi).")
        self.vector.add(ids, docs, metas)
        return {"doc_id": doc_id, "name": filename, "pages": len(pages), "chunks": len(ids),
                "skipped_pages": skipped, "duplicate": False}

    def list_docs(self):
        docs = {}
        for r in self.vector.get():
            d = docs.setdefault(r["meta"]["doc_id"], {"doc_id": r["meta"]["doc_id"], "name": r["meta"]["doc"], "chunks": 0})
            d["chunks"] += 1
        return sorted(docs.values(), key=lambda d: d["name"])

    def delete(self, doc_id):
        self.vector.delete(where={"doc_id": doc_id})

    def has_docs(self):
        return self.vector.count() > 0

    def search(self, query, k=4, min_sim=None):
        min_sim = config.DOC_MIN_SIM if min_sim is None else min_sim
        return [{"text": h["doc"], "doc": h["meta"]["doc"], "page": h["meta"]["page"],
                 "url": h["meta"]["url"], "sim": h["sim"]}
                for h in self.vector.query(query, k=k) if h["sim"] >= min_sim]
