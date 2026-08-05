import ollama
import chromadb

EMBED_MODEL = "bge-m3"
COLLECTION_NAME = "tbc_docs"
VECTOR_DB_DIR = "../vector_db"

client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
collection = client.get_or_create_collection(name=COLLECTION_NAME)

query = "Cuales son los criterios para diagnosticar tuberculosis latente"

embedding = ollama.embeddings(model=EMBED_MODEL, prompt=query)["embedding"]

results = collection.query(query_embeddings=[embedding], n_results=10)

for i, (doc, meta, dist) in enumerate(zip(results["documents"][0], results["metadatas"][0], results["distances"][0])):
    print(f"\n--- Resultado {i+1} (distancia: {dist:.4f}) ---")
    print(f"Fuente: {meta['category']} / {meta['source']}, pagina {meta['page']}")
    print(f"Texto: {doc[:200]}...")