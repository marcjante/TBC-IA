"""
TBC-AI — Fase 7: Indexación de documentos
Recorre /documents recursivamente, extrae texto de cada PDF, lo divide en
fragmentos, genera embeddings con nomic-embed-text y los indexa en Chroma.
La categoría es la carpeta que contiene directamente el PDF (ej. 01_WHO,
02_CDC), para poder filtrar y citar por organismo emisor.
"""

import os
import hashlib
import fitz
import ollama
import chromadb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCUMENTS_DIR = os.path.join(PROJECT_ROOT, "documents")
VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "vector_db")

EMBED_MODEL = "bge-m3"
COLLECTION_NAME = "tbc_docs"

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 300


def find_pdfs(root_dir):
    results = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.lower().endswith(".pdf"):
                full_path = os.path.join(dirpath, fname)
                if os.path.abspath(dirpath) == os.path.abspath(root_dir):
                    category = "sin_categoria"
                else:
                    category = os.path.basename(dirpath)
                results.append((full_path, category, fname))
    return results


def extract_text_by_page(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append((i + 1, text))
    doc.close()
    return pages


MIN_ALNUM_CHARS = 40


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


def main():
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    os.makedirs(VECTOR_DB_DIR, exist_ok=True)

    pdf_entries = find_pdfs(DOCUMENTS_DIR)

    if not pdf_entries:
        print(f"No se encontraron PDF en {DOCUMENTS_DIR} (ni en subcarpetas)")
        return

    print(f"Encontrados {len(pdf_entries)} PDF en total.")
    por_categoria = {}
    for _, cat, _ in pdf_entries:
        por_categoria[cat] = por_categoria.get(cat, 0) + 1
    for cat, n in sorted(por_categoria.items()):
        print(f"  {cat}: {n} documento(s)")

    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    total_chunks = 0

    for full_path, category, fname in pdf_entries:
        print(f"\nProcesando [{category}] {fname}")

        pages = extract_text_by_page(full_path)
        print(f"  Páginas con texto: {len(pages)}")

        doc_chunks = 0
        for page_num, page_text in pages:
            chunks = chunk_text(page_text)

            for idx, chunk in enumerate(chunks):
                cid = chunk_id(f"{category}/{fname}", page_num, idx)

                embedding_response = ollama.embeddings(model=EMBED_MODEL, prompt=chunk)
                embedding = embedding_response["embedding"]

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
                doc_chunks += 1

        print(f"  Fragmentos indexados: {doc_chunks}")

    print(f"\nIndexación completa. Total de fragmentos en la base vectorial: {total_chunks}")
    print(f"Base vectorial guardada en: {VECTOR_DB_DIR}")


if __name__ == "__main__":
    main()
