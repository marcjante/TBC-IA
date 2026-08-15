path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=8,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    STRICT_DISTANCE_THRESHOLD = 480
    LOOSE_DISTANCE_THRESHOLD = 750

    # La lista TB_KEYWORDS solo cubre espanol: en arabe/urdu nunca habria
    # coincidencia, lo que forzaria siempre el umbral estricto (480) aunque
    # la pregunta sea legitima. Como esta app esta dedicada integramente a
    # tuberculosis, tratamos estos dos idiomas como "dentro de dominio" por
    # defecto y usamos el umbral permisivo (750).
    has_keyword = is_tb_related(request.message) or request.lang in ("ar", "ur")

    if not fragments or not distances:
        return {"response": canned_no_info}

    if has_keyword:
        if distances[0] > LOOSE_DISTANCE_THRESHOLD:
            return {"response": canned_no_info}
    else:
        if distances[0] > STRICT_DISTANCE_THRESHOLD:
            return {"response": canned_no_info}

    context_parts = [frag for frag in fragments]
    context_text = "\\n\\n---\\n\\n".join(context_parts)'''

new = '''    PATIENT_TOP_K = 8

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=RERANK_POOL_SIZE,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    STRICT_DISTANCE_THRESHOLD = 480
    LOOSE_DISTANCE_THRESHOLD = 750

    # La lista TB_KEYWORDS solo cubre espanol: en arabe/urdu nunca habria
    # coincidencia, lo que forzaria siempre el umbral estricto (480) aunque
    # la pregunta sea legitima. Como esta app esta dedicada integramente a
    # tuberculosis, tratamos estos dos idiomas como "dentro de dominio" por
    # defecto y usamos el umbral permisivo (750).
    has_keyword = is_tb_related(request.message) or request.lang in ("ar", "ur")

    if not fragments or not distances:
        return {"response": canned_no_info}

    if has_keyword:
        if distances[0] > LOOSE_DISTANCE_THRESHOLD:
            return {"response": canned_no_info}
    else:
        if distances[0] > STRICT_DISTANCE_THRESHOLD:
            return {"response": canned_no_info}

    # El umbral de seguridad ya se evaluo arriba con distances[0] original
    # (pool de RERANK_POOL_SIZE candidatos, sin reordenar). Ahora si,
    # reordenamos y recortamos a los PATIENT_TOP_K que se pasan al modelo.
    fragments, metadatas = rerank_fragments(request.message, fragments, metadatas, distances, PATIENT_TOP_K)

    context_parts = [frag for frag in fragments]
    context_text = "\\n\\n---\\n\\n".join(context_parts)'''

assert old in content, "No se encontro el bloque exacto de /api/patient-chat"
content = content.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Reranking aplicado a /api/patient-chat")
