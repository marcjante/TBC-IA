#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade hybrid_retrieve(): recuperacion hibrida BM25 + ChromaDB (denso),
fusionados con Reciprocal Rank Fusion (RRF), como motor de recuperacion
PRINCIPAL en /api/chat — no solo como fallback (que es lo que hace hoy
el motor complementario, consultado solo si ChromaDB por si solo no es
relevante).

No modifica retrieve() en absoluto (para no arriesgar otros usos que
pueda tener en el codigo) — hybrid_retrieve() hace su propia consulta
directa a ChromaDB para poder casar los resultados de BM25 y densos por
id, y devuelve el MISMO formato (fragments, metadatas, distances) que
retrieve(), para poder sustituirla sin tocar el resto del codigo.

El indice BM25 se construye una vez (la primera consulta tras arrancar
el servidor) y se cachea en memoria — reconstruirlo en cada pregunta
seria demasiado lento. LIMITACION CONOCIDA: si se añaden documentos
nuevos a ChromaDB mientras el servidor esta corriendo, el indice BM25
queda desactualizado hasta reiniciar. Aceptable por ahora: los
documentos de TBC-AI no cambian en caliente durante el uso normal.

Aplica dos parches:
  1. backend/rag.py  -> añade hybrid_retrieve() y su indice BM25 cacheado
  2. backend/main.py -> usa hybrid_retrieve() en vez de retrieve() en
     /api/chat (retrieve() se queda intacta por si se usa en otro sitio)

Uso:
    python3 add_hybrid_retrieve.py "/ruta/a/backend/rag.py" "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# PARCHE 1: backend/rag.py
# ---------------------------------------------------------------

RAG_ANCHOR = '''def is_relevant(fragments, distances, has_keyword):'''

RAG_ADDITION = '''_bm25_index = None
_bm25_ids = None
_bm25_docs = None
_bm25_metas = None


def _build_bm25_index():
    """Construye el indice BM25 sobre TODO el corpus de ChromaDB (no solo
    los top_k de una consulta). Se llama una sola vez, la primera vez que
    se necesita, y se cachea en variables de modulo."""
    global _bm25_index, _bm25_ids, _bm25_docs, _bm25_metas
    import re
    from rank_bm25 import BM25Okapi

    all_data = collection.get(include=["documents", "metadatas"])
    _bm25_ids = all_data["ids"]
    _bm25_docs = all_data["documents"]
    _bm25_metas = all_data["metadatas"]

    tokenized_corpus = [re.findall(r"\\w+", (doc or "").lower()) for doc in _bm25_docs]
    _bm25_index = BM25Okapi(tokenized_corpus)


def _get_bm25_index():
    if _bm25_index is None:
        _build_bm25_index()
    return _bm25_index, _bm25_ids, _bm25_docs, _bm25_metas


def hybrid_retrieve(query_text, top_k):
    """Recuperacion hibrida: BM25 + ChromaDB denso, fusionados con
    Reciprocal Rank Fusion (RRF). Pensada para sustituir a retrieve()
    como motor PRINCIPAL (Fase 2 de la propuesta de arquitectura TBC-AI
    v2, agosto 2026) — antes BM25 solo entraba via el motor
    complementario, y unicamente cuando ChromaDB por si solo no era
    relevante.

    Devuelve (fragments, metadatas, distances) en el MISMO formato que
    retrieve(), para poder sustituirla sin cambiar el resto del codigo.
    Fail-open: si BM25 falla por cualquier motivo, se usa solo el
    resultado denso de ChromaDB (el comportamiento de retrieve() de
    siempre), nunca rompe la recuperacion."""
    import re
    import numpy as np

    fetch_k = max(top_k * 3, 30)

    # --- Denso (ChromaDB), consulta directa para tener acceso a los ids ---
    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + query_text)["embedding"]
    dense_results = collection.query(query_embeddings=[query_embedding], n_results=fetch_k)
    dense_ids = dense_results["ids"][0] if dense_results["ids"] else []
    dense_docs = dense_results["documents"][0] if dense_results["documents"] else []
    dense_metas = dense_results["metadatas"][0] if dense_results["metadatas"] else []
    dense_distances = dense_results["distances"][0] if dense_results["distances"] else []

    if not dense_ids:
        return [], [], []

    dense_lookup = {
        doc_id: (doc, meta, dist)
        for doc_id, doc, meta, dist in zip(dense_ids, dense_docs, dense_metas, dense_distances)
    }

    # --- BM25 sobre el mismo corpus completo (indice cacheado) ---
    try:
        bm25_index, bm25_ids, bm25_docs, bm25_metas = _get_bm25_index()
        tokenized_query = re.findall(r"\\w+", query_text.lower())
        bm25_scores = bm25_index.get_scores(tokenized_query)
        bm25_top_local = np.argsort(bm25_scores)[::-1][:fetch_k]
        bm25_ranked_ids = [bm25_ids[i] for i in bm25_top_local]
        bm25_lookup = {bm25_ids[i]: (bm25_docs[i], bm25_metas[i]) for i in bm25_top_local}
    except Exception as e:
        print(f"[DEBUG hybrid_retrieve] BM25 fallo, usando solo denso: {type(e).__name__}: {e}")
        bm25_ranked_ids = []
        bm25_lookup = {}

    # --- Fusion RRF por id ---
    k_rrf = 60
    rrf_scores = {}
    for rank, doc_id in enumerate(dense_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)
    for rank, doc_id in enumerate(bm25_ranked_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)

    fused_ids = [doc_id for doc_id, _ in sorted(rrf_scores.items(), key=lambda x: -x[1])][:top_k]

    # Reconstruir en el orden fusionado. Si el id viene de la busqueda
    # densa, usamos su distancia real. Si solo aparece via BM25 (no
    # estaba entre los top de ChromaDB), no hay distancia de embeddings
    # real disponible: usamos como valor centinela el umbral estricto,
    # ni lo descarta ni lo prioriza artificialmente en is_relevant().
    fragments, metadatas, distances = [], [], []
    for doc_id in fused_ids:
        if doc_id in dense_lookup:
            doc, meta, dist = dense_lookup[doc_id]
        elif doc_id in bm25_lookup:
            doc, meta = bm25_lookup[doc_id]
            dist = STRICT_DISTANCE_THRESHOLD
        else:
            continue
        fragments.append(doc)
        metadatas.append(meta)
        distances.append(dist)

    return fragments, metadatas, distances


def is_relevant(fragments, distances, has_keyword):'''


# ---------------------------------------------------------------
# PARCHE 2: backend/main.py
# ---------------------------------------------------------------

MAIN_IMPORT_OLD = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response, query_master_bibliography, search_pubmed_live, get_drug_safety_info"
MAIN_IMPORT_NEW = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response, query_master_bibliography, search_pubmed_live, get_drug_safety_info, hybrid_retrieve"

MAIN_CALL_OLD = '''    retrieval_query = build_retrieval_query(request.message, request.history)
    retrieval_query = expand_query(retrieval_query)
    fragments, metadatas, distances = retrieve(retrieval_query, request.top_k)'''

MAIN_CALL_NEW = '''    retrieval_query = build_retrieval_query(request.message, request.history)
    retrieval_query = expand_query(retrieval_query)
    fragments, metadatas, distances = hybrid_retrieve(retrieval_query, request.top_k)'''


def apply_patch(path, old, new, label):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if new in content:
        print(f"  {label}: ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(old)
    if count == 0:
        print(f"  {label}: ABORTADO, no se encontró el bloque esperado. No se ha escrito nada.")
        sys.exit(1)
    if count > 1:
        print(f"  {label}: ABORTADO, el bloque aparece {count} veces (debería ser único). No se ha escrito nada.")
        sys.exit(1)

    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  {label}: aplicado correctamente.")


def main():
    if len(sys.argv) != 3:
        print("Uso: python3 add_hybrid_retrieve.py <ruta a backend/rag.py> <ruta a backend/main.py>")
        sys.exit(1)

    rag_path, main_path = sys.argv[1], sys.argv[2]

    print(f"Parcheando {rag_path}...")
    apply_patch(rag_path, RAG_ANCHOR, RAG_ADDITION, "rag.py (hybrid_retrieve + indice BM25)")

    print(f"Parcheando {main_path}...")
    apply_patch(main_path, MAIN_IMPORT_OLD, MAIN_IMPORT_NEW, "main.py (import)")
    apply_patch(main_path, MAIN_CALL_OLD, MAIN_CALL_NEW, "main.py (usar hybrid_retrieve)")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
