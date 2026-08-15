"""
TBC-AI - backend/rag.py

Todo lo relacionado con la recuperacion de informacion (Retrieval-Augmented
Generation):
- chunk_text() / chunk_id(): fragmentacion de texto para indexar.
- index_single_pdf(): indexacion de un PDF individual (usado por /api/upload
  y por scripts/index_documents.py de forma equivalente).
- retrieve(): consulta a ChromaDB, devuelve fragmentos/metadatos/distancias.
- is_relevant(): aplica el filtro de doble umbral (estricto/permisivo).

FASE 7 de la auditoria: extraido de main.py. Los dos endpoints de chat
(/api/chat y /api/patient-chat) llamaban a una version casi identica de
esta logica cada uno por su lado; aqui queda unificada en un solo sitio.
Los umbrales (480/750) NO se han cambiado respecto al original.
"""

import hashlib
import fitz
import ollama

from backend.config import EMBED_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, MIN_ALNUM_CHARS, collection

STRICT_DISTANCE_THRESHOLD = 480
LOOSE_DISTANCE_THRESHOLD = 750


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            alnum_count = sum(1 for c in chunk if c.isalnum())
            if alnum_count >= MIN_ALNUM_CHARS:
                chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def chunk_id(source_file, page_num, chunk_index):
    raw = f"{source_file}|{page_num}|{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def index_single_pdf(pdf_path, category, fname):
    doc = fitz.open(pdf_path)
    total_chunks = 0

    for i, page in enumerate(doc):
        page_num = i + 1
        text = page.get_text().strip()
        if not text:
            continue

        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            cid = chunk_id(f"{category}/{fname}", page_num, idx)
            embedding = ollama.embeddings(model=EMBED_MODEL, prompt=chunk)["embedding"]

            collection.upsert(
                ids=[cid],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "source": fname,
                    "category": category,
                    "page": page_num,
                }],
            )
            total_chunks += 1

    doc.close()
    return total_chunks


def retrieve(query_text, top_k):
    """Genera el embedding de la pregunta (con el prefijo fijo 'Tuberculosis: '
    que mejora la recuperacion en preguntas cortas) y consulta la coleccion.
    Devuelve (fragments, metadatas, distances), cada uno una lista, vacias
    si no hay resultados."""
    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + query_text)["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []
    return fragments, metadatas, distances


def is_relevant(fragments, distances, has_keyword):
    """Aplica el filtro de doble umbral: si la pregunta contiene una palabra
    clave relacionada con tuberculosis, se usa el umbral permisivo (750);
    si no, el estricto (480). Devuelve False si no hay fragmentos o si la
    distancia del mejor resultado supera el umbral aplicable."""
    if not fragments or not distances:
        return False
    threshold = LOOSE_DISTANCE_THRESHOLD if has_keyword else STRICT_DISTANCE_THRESHOLD
    return distances[0] <= threshold
