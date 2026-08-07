path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    final_response = response["message"]["content"]
    normalized_check = final_response.lower()
    leaked = any(pat in normalized_check for pat in [
        "sin embargo, puedo ofrecerte", "informacion general sobre",
        "segun mi conocimiento", "de manera general,",
    ])
    if leaked:
        final_response = "No encuentro esta informacion en los documentos disponibles."'''

new = '''    final_response = response["message"]["content"]
    normalized_check = final_response.lower()

    CANNED_NO_INFO_PATIENT = "No encuentro esta informacion en los documentos disponibles."

    # Si el modelo expresa "no lo se" con sus propias palabras (con o sin
    # rodeos tipo "lo siento"), lo normalizamos a la frase fija, en vez de
    # dejar pasar variantes que no coinciden exactamente y contaminan las
    # estadisticas de "con respuesta / sin cobertura".
    no_info_variants = [
        "no encuentro esta informacion", "no encuentro informacion",
        "no tengo esta informacion", "no tengo informacion",
        "no dispongo de esta informacion", "no dispongo de informacion",
        "no cuento con esta informacion", "no cuento con informacion",
    ]
    said_no_info = any(v in normalized_check for v in no_info_variants)

    leaked = any(pat in normalized_check for pat in [
        "sin embargo, puedo ofrecerte", "informacion general sobre",
        "segun mi conocimiento", "de manera general,",
        "puedo ofrecerte", "puedo darte informacion general",
    ])

    if said_no_info or leaked:
        final_response = CANNED_NO_INFO_PATIENT'''

assert old in content, "No se encontro el bloque exacto de leaked en patient_chat"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Guard de fuga de patient_chat ampliado")
