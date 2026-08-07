path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=request.top_k,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []

    if not fragments:
        return {
            "response": "No encuentro esta informacion en los documentos disponibles.",
            "sources": [],
        }'''

new = '''    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=request.top_k,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    RELEVANCE_THRESHOLD = 650

    if not fragments or not distances or distances[0] > RELEVANCE_THRESHOLD:
        return {
            "response": "No encuentro esta informacion en los documentos disponibles.",
            "sources": [],
        }'''

assert old in content, "No se encontro el bloque exacto a reemplazar"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Filtro de relevancia aplicado (umbral 650)")
