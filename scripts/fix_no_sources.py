path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    return {
        "response": response["message"]["content"],
        "sources": sources_used,
    }'''

new = '''    final_response = response["message"]["content"]
    no_info_phrase = "No encuentro esta informacion en los documentos disponibles"
    if final_response.strip().startswith(no_info_phrase):
        sources_used = []

    return {
        "response": final_response,
        "sources": sources_used,
    }'''

assert old in content, "No se encontro el bloque exacto de retorno"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Correccion aplicada: sin fuentes cuando no hay informacion")
