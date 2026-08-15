"""
TBC-AI - scripts/experiment_reranking.py

FASE 6 (exploracion, no produccion): compara la seleccion de fragmentos
actual (top-8 puro por distancia vectorial) contra una seleccion con
reranking hibrido (distancia vectorial + solapamiento de palabras clave),
sobre un conjunto de preguntas de prueba conocidas.

Este script NO modifica backend/main.py ni el comportamiento real del
sistema. Es solo para decidir, con evidencia, si merece la pena adoptar
el reranking antes de tocar produccion.

Uso:
    python3 scripts/experiment_reranking.py
"""

import os
import re
import chromadb
import ollama

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "vector_db")
COLLECTION_NAME = "tbc_docs"
EMBED_MODEL = os.environ.get("TBC_EMBED_MODEL", "bge-m3")

CANDIDATE_POOL_SIZE = 20  # cuantos fragmentos se recuperan antes de reordenar
FINAL_TOP_K = 8           # cuantos se quedan al final (igual que produccion hoy)

TEST_QUERIES = [
    "Es segura la pirazinamida durante el embarazo?",
    "Que es el linezolid y que hay que monitorizar?",
    "Que diferencia hay entre Mantoux e IGRA?",
    "Que es la BCG?",
    "Cuanto dura el tratamiento?",
]


def normalize(text):
    t = text.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]:
        t = t.replace(a, b)
    return t


def keyword_overlap_score(query, fragment_text):
    """Cuenta cuantas palabras 'significativas' (>=4 letras) de la pregunta
    aparecen literalmente en el fragmento. Puntuacion simple, sin pesos
    TF-IDF, a proposito: el objetivo es una primera exploracion barata,
    no un sistema de reranking definitivo."""
    query_words = set(w for w in re.findall(r"[a-z]+", normalize(query)) if len(w) >= 4)
    frag_norm = normalize(fragment_text)
    matches = sum(1 for w in query_words if w in frag_norm)
    return matches


def retrieve_pool(collection, query, pool_size):
    embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + query)["embedding"]
    results = collection.query(query_embeddings=[embedding], n_results=pool_size)
    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []
    return list(zip(fragments, metadatas, distances))


def rerank_hybrid(query, pool):
    """Combina distancia vectorial (menor es mejor) con solapamiento de
    palabras clave (mayor es mejor) en una puntuacion unica. La distancia
    se normaliza a un rango comparable restando un bonus proporcional a
    los matches de palabras clave, en vez de una formula compleja."""
    scored = []
    for frag, meta, dist in pool:
        kw_score = keyword_overlap_score(query, frag)
        # Cada palabra clave coincidente resta 40 puntos de distancia
        # (aprox equivalente a acercar el fragmento un umbral de relevancia).
        adjusted_distance = dist - (kw_score * 40)
        scored.append((frag, meta, dist, kw_score, adjusted_distance))
    scored.sort(key=lambda x: x[4])
    return scored


def summarize_selection(label, items, top_k):
    print(f"  {label}:")
    for i, item in enumerate(items[:top_k], 1):
        if len(item) == 3:
            frag, meta, dist = item
            print(f"    {i}. {meta.get('source')} (dist={dist:.1f})")
        else:
            frag, meta, dist, kw, adj = item
            print(f"    {i}. {meta.get('source')} (dist={dist:.1f}, kw_matches={kw}, ajustada={adj:.1f})")


def main():
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    for query in TEST_QUERIES:
        print(f"\n=== Pregunta: {query} ===")
        pool = retrieve_pool(collection, query, CANDIDATE_POOL_SIZE)

        # Seleccion actual (produccion): simplemente los primeros 8 por distancia.
        current_selection = pool[:FINAL_TOP_K]
        summarize_selection("SIN reranking (produccion actual)", current_selection, FINAL_TOP_K)

        reranked = rerank_hybrid(query, pool)
        summarize_selection("CON reranking hibrido", reranked, FINAL_TOP_K)

        current_sources = set(m.get("source") for _, m, _ in current_selection)
        reranked_sources = set(m.get("source") for f, m, d, kw, adj in reranked[:FINAL_TOP_K])
        diff = reranked_sources - current_sources
        if diff:
            print(f"  >> El reranking introdujo fragmentos nuevos en el top-{FINAL_TOP_K}: {diff}")
        else:
            print(f"  >> Sin cambios en el conjunto de fragmentos seleccionados.")


if __name__ == "__main__":
    main()
