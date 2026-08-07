import re

files_to_patch = ["scripts/index_documents.py", "backend/main.py"]

old_chunk_text = '''def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks'''

new_chunk_text = '''MIN_ALNUM_CHARS = 40


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
    return chunks'''

for path in files_to_patch:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert old_chunk_text in content, f"No se encontro chunk_text en {path}"
    content = content.replace(old_chunk_text, new_chunk_text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{path}: filtro de fragmentos degenerados aplicado")

print("\nListo. Hay que reindexar para que el filtro tenga efecto.")
