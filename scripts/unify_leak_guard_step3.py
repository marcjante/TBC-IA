path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    leaked = any(pat in normalized_check for pat in [
        "sin embargo, puedo ofrecerte", "informacion general sobre",
        "segun mi conocimiento", "de manera general,",
        "puedo ofrecerte", "puedo darte informacion general",
    ])'''

new = '''    leaked = detect_generic_knowledge_leak(final_response)'''

assert old in content, "No se encontro el bloque exacto de /api/patient-chat a reemplazar"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("api/patient-chat ahora usa la funcion compartida")
