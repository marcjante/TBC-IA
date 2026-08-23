"""
TBC-AI - backend/rag.py

Todo lo relacionado con la recuperacion de informacion (Retrieval-Augmented
Generation):
- chunk_text() / chunk_id(): fragmentacion de texto para indexar.
- index_single_pdf(): indexacion de un PDF individual (usado por /api/upload
  y por scripts/index_documents.py de forma equivalente).
- retrieve(): consulta a ChromaDB, devuelve fragmentos/metadatos/distancias.
- is_relevant(): aplica el filtro de doble umbral (estricto/permisivo).
- query_sota_fallback(): consulta el motor tbc-ia-sota-engine cuando
  ChromaDB no encuentra nada suficientemente relevante (agosto 2026).

FASE 7 de la auditoria: extraido de main.py. Los dos endpoints de chat
(/api/chat y /api/patient-chat) llamaban a una version casi identica de
esta logica cada uno por su lado; aqui queda unificada en un solo sitio.
Los umbrales (480/750) NO se han cambiado respecto al original.
"""

import hashlib
import fitz
import ollama
import requests

from backend.config import (
    EMBED_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, MIN_ALNUM_CHARS, collection,
    SOTA_ENGINE_URL, SOTA_ENGINE_API_KEY,
)

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


def query_sota_fallback(query_text, timeout=8):
    """Consulta el motor tbc-ia-sota-engine (recuperacion hibrida BM25+denso
    con reranking, servido aparte en http://127.0.0.1:8000) cuando ChromaDB
    no ha encontrado nada suficientemente relevante (is_relevant() == False).

    Devuelve una tupla (fragments, metadatas, info):
    - Si el motor detecta una alerta clinica (ej. toxicidad ocular por
      etambutol), info = {"alert": [...]} y fragments/metadatas van vacios:
      quien llama debe mostrar la alerta, no generar una respuesta libre.
    - Si hay evidencia con confianza suficiente (no LOW/INSUFFICIENT),
      devuelve fragments/metadatas en el mismo formato que retrieve(), e
      info = {"confidence": "...", "source": "sota_engine"}.
    - Si el motor no responde, falla, o no hay evidencia util, devuelve
      ([], [], None) para que quien llama use el mensaje de "sin cobertura"
      habitual sin romper el flujo.

    No lanza excepciones hacia arriba: cualquier fallo de red o de formato
    se trata como "sin evidencia adicional", nunca como error 500 para el
    usuario final.
    """
    try:
        resp = requests.post(
            f"{SOTA_ENGINE_URL}/v1/evidence",
            params={"query": query_text},
            headers={"X-API-Key": SOTA_ENGINE_API_KEY},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return [], [], None

    if data.get("alerts"):
        return [], [], {"alert": data["alerts"]}

    confidence = data.get("confidence_level")
    evidence = data.get("grounded_evidence", [])
    if not evidence or confidence in (None, "INSUFFICIENT", "LOW"):
        return [], [], None

    fragments = [e.get("content", "") for e in evidence]
    metadatas = [
        {
            "source": "TBC-IA Knowledge Base (motor de recuperación complementario)",
            "category": e.get("document_id", ""),
            "page": None,
        }
        for e in evidence
    ]
    return fragments, metadatas, {"confidence": confidence, "source": "sota_engine"}


def verify_groundedness(response_text, sources, timeout=15):
    """Consulta /v1/verify_groundedness en el motor complementario para
    detectar frases de una respuesta ya generada que no estan respaldadas
    por ninguna fuente (fabricacion silenciosa del LLM, sin frase de aviso
    reconocible por LEAK_PATTERNS/REFUSAL_PATTERNS en safety.py).

    NO decide nada sobre la respuesta: solo informa. Devuelve None si el
    motor no responde o falla (fail-open: nunca bloquea el flujo normal
    por un problema de este chequeo adicional, que todavia esta sin
    calibrar contra casos reales — ver aviso en tbc-ia-sota-engine/app/main.py).
    """
    if not sources:
        return None
    try:
        resp = requests.post(
            f"{SOTA_ENGINE_URL}/v1/verify_groundedness",
            json={"response_text": response_text, "sources": sources},
            headers={"X-API-Key": SOTA_ENGINE_API_KEY},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


LLAMAFILE_URL = "http://127.0.0.1:8081"


def query_llamafile_response(context_text, question, timeout=30):
    """Genera una respuesta independiente con un segundo modelo (Mistral 7B
    via Llamafile, servido aparte en http://127.0.0.1:8081) para la misma
    pregunta y el mismo contexto que uso Ollama. Es la mitad "B" del
    consenso entre dos modelos (señal secundaria, ver compare_with_llamafile
    en main.py) - probado hoy como prototipo en dual_model_check.py.

    Fail-open: devuelve None si el servidor no responde, esta caido, o el
    formato de respuesta no es el esperado. Nunca lanza excepcion, para no
    romper el flujo normal de /api/chat si Llamafile no esta corriendo."""
    system_prompt = (
        "Eres un asistente clinico. Responde la pregunta del paciente "
        "usando exclusivamente el CONTEXTO proporcionado. No inventes "
        "informacion que no este en el contexto."
    )
    user_prompt = f"CONTEXTO:\n{context_text}\n\nPREGUNTA:\n{question}"
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    try:
        resp = requests.post(f"{LLAMAFILE_URL}/v1/chat/completions", json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None
