path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    final_response = response["message"]["content"]
    no_info_phrase = "No encuentro esta informaci"
    CANNED_NO_INFO = "No encuentro esta informacion en los documentos disponibles."

    leaked = detect_generic_knowledge_leak(final_response)

    if final_response.strip().startswith(no_info_phrase):
        sources_used = []
    elif leaked:
        final_response = CANNED_NO_INFO
        sources_used = []'''

new = '''    final_response = response["message"]["content"]
    no_info_phrase = "No encuentro esta informaci"
    CANNED_NO_INFO = "No encuentro esta informacion en los documentos disponibles."

    leaked = detect_generic_knowledge_leak(final_response)

    # Se busca la frase fija en cualquier parte de la respuesta, no solo al
    # principio: el modelo a veces la antepone con texto propio (ej. "La
    # respuesta es: No encuentro..."), lo que antes hacia que no se vaciaran
    # las fuentes aunque el propio modelo diga que no sabe la respuesta.
    if no_info_phrase in final_response:
        final_response = CANNED_NO_INFO
        sources_used = []
    elif leaked:
        final_response = CANNED_NO_INFO
        sources_used = []'''

assert old in content, "No se encontro el bloque exacto a corregir"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Deteccion de frase fija ampliada a toda la respuesta")
