"""
TBC-AI - scripts/index_json_knowledgebase.py

Indexa la base de conocimiento clinica estructurada en JSON
(TBC_KNOWLEDGEBASE_V9, version acumulativa) en la misma coleccion Chroma
que usan los PDF de OMS/CDC/ECDC, para que el RAG pueda recuperar tambien
este contenido.

DIFERENCIA CLAVE con index_documents.py:
- index_documents.py lee PDF con PyMuPDF.
- Este script lee fichas JSON (drugs/, adverse_effects/, special_populations/,
  interactions/), las convierte a texto legible preservando su estructura,
  y resuelve cada referencia (evidence_ids / sources) contra
  03_METADATA/bibliography.json para adjuntar una cita completa y trazable
  (titulo, año, revista/editor, URL, PMID/DOI) al final de cada fragmento.

Metadatos asignados a cada fragmento:
- source: ruta relativa del fichero JSON de origen (ej. "drugs/linezolid/linezolid_rag.json")
- category: "05_ClinicalKB_JSON" (categoria dedicada, nunca se confunde con
  los PDF de OMS/CDC/ECDC ya indexados)
- page: 0 (no aplica paginacion a JSON; se mantiene el campo por compatibilidad)

Idempotente: cada fragmento tiene un ID determinista basado en la ruta del
archivo y el indice del fragmento, asi que volver a ejecutar el script
actualiza (upsert) en vez de duplicar.

Uso:
    python3 scripts/index_json_knowledgebase.py --source TBC_KNOWLEDGEBASE_V9
"""

import json
import os
import sys
import argparse
import hashlib

import chromadb
import ollama

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "vector_db")
COLLECTION_NAME = "tbc_docs"
EMBED_MODEL = os.environ.get("TBC_EMBED_MODEL", "bge-m3")
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 300
MIN_ALNUM_CHARS = 40
NEW_CATEGORY = "05_ClinicalKB_JSON"


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Misma logica de fragmentacion que index_documents.py, para mantener
    consistencia con el resto de la base vectorial."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        alnum_count = sum(1 for c in chunk if c.isalnum())
        if alnum_count >= MIN_ALNUM_CHARS:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def load_bibliography(kb_root):
    path = os.path.join(kb_root, "03_METADATA", "bibliography.json")
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["id"]: e for e in entries if "id" in e}


def as_text(value):
    """Convierte cualquier valor (str, int, float, None) a texto limpio.
    Los campos de bibliography.json no siempre vienen como string: la
    mayoria de los 'pmid' estan almacenados como numero flotante (ej.
    40693952.0 en vez de "40693952"). Se normalizan a entero cuando el
    float representa un numero entero, para no mostrar el ".0" final."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def format_citation(entry):
    if not entry:
        return None
    parts = [as_text(entry.get("title"))]
    author = as_text(entry.get("authors"))
    year = as_text(entry.get("year"))
    journal = as_text(entry.get("journal_or_publisher"))
    if author:
        parts.append(author)
    if journal:
        parts.append(journal)
    if year:
        parts.append(year)
    url = as_text(entry.get("url"))
    doi = as_text(entry.get("doi"))
    pmid = as_text(entry.get("pmid"))
    tail = []
    if doi:
        tail.append(f"DOI: {doi}")
    if pmid:
        tail.append(f"PMID: {pmid}")
    if url:
        tail.append(url)
    citation = " | ".join(p for p in parts if p)
    if tail:
        citation += " (" + "; ".join(tail) + ")"
    return citation


def collect_evidence_ids(obj, found=None):
    """Recorre recursivamente el JSON buscando cualquier lista bajo una
    clave 'sources' o 'evidence_ids', sin asumir una unica estructura fija
    (los ficheros no son 100% homogeneos entre si)."""
    if found is None:
        found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("sources", "evidence_ids") and isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        found.add(item)
            else:
                collect_evidence_ids(v, found)
    elif isinstance(obj, list):
        for item in obj:
            collect_evidence_ids(item, found)
    return found


def json_to_readable_text(data, indent=0):
    """Convierte de forma generica un objeto JSON (dict/list/valor) en texto
    legible, preservando la jerarquia mediante indentacion y encabezados,
    sin asumir un esquema fijo (los 35 ficheros no comparten exactamente
    la misma estructura)."""
    lines = []
    pad = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ("sources", "evidence_ids"):
                continue  # se listan aparte, al final, como citas resueltas
            label = key.replace("_", " ").strip().capitalize()
            if isinstance(value, (dict, list)):
                lines.append(f"{pad}{label}:")
                lines.append(json_to_readable_text(value, indent + 1))
            else:
                lines.append(f"{pad}{label}: {value}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(json_to_readable_text(item, indent))
            else:
                lines.append(f"{pad}- {item}")
    else:
        lines.append(f"{pad}{data}")
    return "\n".join(line for line in lines if line.strip())


def build_document_text(json_path, kb_root, bibliography):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    rel_path = os.path.relpath(json_path, kb_root)
    title = data.get("topic") or data.get("drug") or data.get("topic_id") or rel_path

    body = json_to_readable_text(data)

    evidence_ids = sorted(collect_evidence_ids(data))
    citations = []
    for eid in evidence_ids:
        entry = bibliography.get(eid)
        citation = format_citation(entry)
        if citation:
            citations.append(f"[{eid}] {citation}")
        else:
            citations.append(f"[{eid}] (referencia no encontrada en bibliography.json)")

    sources_block = "\n".join(citations) if citations else "Sin referencias bibliograficas asociadas."

    full_text = (
        f"Ficha de base de conocimiento clinica: {title}\n"
        f"(Fuente interna: {rel_path})\n\n"
        f"{body}\n\n"
        f"--- Fuentes bibliograficas de esta ficha ---\n"
        f"{sources_block}\n"
    )
    return full_text, rel_path


def deterministic_id(rel_path, chunk_index):
    h = hashlib.sha1(f"{rel_path}::{chunk_index}".encode("utf-8")).hexdigest()[:16]
    return f"jsonkb_{h}"


def main():
    parser = argparse.ArgumentParser(description="Indexa la base de conocimiento clinica JSON")
    parser.add_argument("--source", required=True, help="Carpeta raiz del knowledge base extraido (ej. TBC_KNOWLEDGEBASE_V9)")
    args = parser.parse_args()

    kb_root = os.path.abspath(args.source)
    if not os.path.isdir(kb_root):
        print(f"ERROR: no existe la carpeta {kb_root}")
        sys.exit(1)

    bibliography = load_bibliography(kb_root)
    print(f"Bibliografia cargada: {len(bibliography)} referencias")

    rag_files = []
    for root, _, files in os.walk(kb_root):
        for fname in files:
            if fname.endswith("_rag.json"):
                rag_files.append(os.path.join(root, fname))
    rag_files.sort()
    print(f"Fichas RAG encontradas: {len(rag_files)}")

    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    total_chunks = 0
    for json_path in rag_files:
        full_text, rel_path = build_document_text(json_path, kb_root, bibliography)
        chunks = chunk_text(full_text)

        if not chunks:
            print(f"AVISO: {rel_path} no genero ningun fragmento valido (muy corto), se omite.")
            continue

        ids = [deterministic_id(rel_path, i) for i in range(len(chunks))]
        metadatas = [{"source": rel_path, "category": NEW_CATEGORY, "page": 0} for _ in chunks]

        embeddings = []
        for chunk in chunks:
            emb = ollama.embeddings(model=EMBED_MODEL, prompt=chunk)["embedding"]
            embeddings.append(emb)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )
        total_chunks += len(chunks)
        print(f"Indexado: {rel_path} ({len(chunks)} fragmento(s))")

    print(f"\nCompletado. Total fragmentos indexados/actualizados: {total_chunks}")
    print(f"Total documentos en la coleccion tras esta operacion: {collection.count()}")


if __name__ == "__main__":
    main()
