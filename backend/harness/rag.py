"""RAG pipeline: document text extraction, chunking, and TF-IDF retrieval.

Uses TF-IDF cosine similarity (scikit-learn) for retrieval, which is robust and
dependency-light (the Ollama Cloud key does not expose embedding models).
"""
import io
import csv
from pypdf import PdfReader
from docx import Document as DocxDocument
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if name.endswith(".csv"):
        text = data.decode("utf-8", errors="ignore")
        rows = list(csv.reader(io.StringIO(text)))
        return "\n".join(" | ".join(r) for r in rows)
    # txt / md / fallback
    return data.decode("utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200):
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, chunk_size - overlap)
    approx_words = max(50, chunk_size // 6)
    step_words = max(1, approx_words - (overlap // 6))
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + approx_words]).strip()
        if chunk:
            chunks.append(chunk)
        i += step_words
    return chunks


def retrieve(query: str, chunk_docs: list, top_k: int = 4):
    """chunk_docs: list of dicts with keys text, document_id, document_name, index.
    Returns top_k chunks with a similarity score attached."""
    if not chunk_docs:
        return []
    texts = [c["text"] for c in chunk_docs]
    try:
        vect = TfidfVectorizer(stop_words="english", max_features=8000)
        matrix = vect.fit_transform(texts + [query])
    except ValueError:
        return []
    query_vec = matrix[-1]
    doc_matrix = matrix[:-1]
    sims = cosine_similarity(query_vec, doc_matrix)[0]
    ranked = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
    results = []
    for idx in ranked[:top_k]:
        if sims[idx] <= 0:
            continue
        c = dict(chunk_docs[idx])
        c["score"] = round(float(sims[idx]), 4)
        results.append(c)
    return results
