path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=request.top_k,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    STRICT_DISTANCE_THRESHOLD = 480
    LOOSE_DISTANCE_THRESHOLD = 750

    has_keyword = is_tb_related(request.message)'''

new = '''    # FASE 6: se recupera un pool mas amplio (RERANK_POOL_SIZE) del que se
    # usa finalmente (request.top_k), para poder reordenar por relevancia
    # antes de quedarnos con los top_k que realmente ve el modelo. El
    # umbral de seguridad (mas abajo) sigue basandose en distances[0] del
    # orden vectorial ORIGINAL, sin reordenar, para no repetir el problema
    # de alucinacion que aparecio al subir top_k directamente en pruebas
    # anteriores.
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(request.top_k, RERANK_POOL_SIZE),
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    STRICT_DISTANCE_THRESHOLD = 480
    LOOSE_DISTANCE_THRESHOLD = 750

    has_keyword = is_tb_related(request.message)'''

assert old in content, "No se encontro el bloque de recuperacion de /api/chat"
content = content.replace(old, new, 1)

old2 = '''    context_parts = []
    sources_used = []
    for frag, meta in zip(fragments, metadatas):'''

new2 = '''    # El umbral de seguridad ya se evaluo arriba con distances[0] original.
    # Ahora si, reordenamos y recortamos a los top_k que se pasan al modelo.
    fragments, metadatas = rerank_fragments(request.message, fragments, metadatas, distances, request.top_k)

    context_parts = []
    sources_used = []
    for frag, meta in zip(fragments, metadatas):'''

assert old2 in content, "No se encontro el bloque de construccion de contexto de /api/chat"
content = content.replace(old2, new2, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Reranking aplicado a /api/chat")
