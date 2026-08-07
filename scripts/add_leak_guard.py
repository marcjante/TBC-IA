path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    final_response = response["message"]["content"]
    no_info_phrase = "No encuentro esta informaci"
    if final_response.strip().startswith(no_info_phrase):
        sources_used = []'''

new = '''    final_response = response["message"]["content"]
    no_info_phrase = "No encuentro esta informaci"
    CANNED_NO_INFO = "No encuentro esta informacion en los documentos disponibles."

    LEAK_PATTERNS = [
        "no contiene informacion especifica",
        "no contiene informaci\\u00f3n especifica",
        "sin embargo, puedo ofrecerte",
        "puedo ofrecerte informacion general",
        "informacion general sobre",
        "de manera general,",
        "por lo general,",
        "seg\\u00fan mi conocimiento",
        "segun mi conocimiento",
        "el texto proporcionado no",
        "el contexto no contiene",
        "no se menciona expl\\u00edcitamente",
        "no se menciona explicitamente",
    ]

    def normalize_for_check(text):
        t = text.lower()
        for a, b in [("\\u00e1", "a"), ("\\u00e9", "e"), ("\\u00ed", "i"), ("\\u00f3", "o"), ("\\u00fa", "u")]:
            t = t.replace(a, b)
        return t

    normalized_response = normalize_for_check(final_response)
    leaked = any(pat in normalize_for_check(pat) and normalize_for_check(pat) in normalized_response for pat in LEAK_PATTERNS)
    leaked = any(normalize_for_check(pat) in normalized_response for pat in LEAK_PATTERNS)

    if final_response.strip().startswith(no_info_phrase):
        sources_used = []
    elif leaked:
        final_response = CANNED_NO_INFO
        sources_used = []'''

assert old in content, "No se encontro el bloque exacto a reemplazar"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Guard de codigo contra fugas de conocimiento general aplicado")
