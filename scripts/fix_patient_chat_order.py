path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''@app.post("/api/patient-chat")
def patient_chat(request: PatientChatRequest):
    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + request.message)["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=8,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    STRICT_DISTANCE_THRESHOLD = 480
    LOOSE_DISTANCE_THRESHOLD = 750

    has_keyword = is_tb_related(request.message)

    if not fragments or not distances:
        return {"response": canned_no_info}

    if has_keyword:
        if distances[0] > LOOSE_DISTANCE_THRESHOLD:
            return {"response": canned_no_info}
    else:
        if distances[0] > STRICT_DISTANCE_THRESHOLD:
            return {"response": canned_no_info}

    context_parts = [frag for frag in fragments]
    context_text = "\\n\\n---\\n\\n".join(context_parts)

    LANG_NAMES = {
        "ca": "catalan",
        "es": "castellano",
        "ar": "arabe (fusha / arabe estandar, para que lo entienda tambien un hablante de darija marroqui)",
        "ur": "urdu",
    }
    lang_name = LANG_NAMES.get(request.lang, "castellano")
    user_prompt = f"IDIOMA DE RESPUESTA: {lang_name}\\n\\nCONTEXTO:\\n{context_text}\\n\\nPREGUNTA DEL PACIENTE:\\n{request.message}"'''

new = '''@app.post("/api/patient-chat")
def patient_chat(request: PatientChatRequest):
    # Nombres de idioma y mensaje fijo de "sin informacion" en cada idioma,
    # definidos al principio de la funcion para poder usarlos en cualquier
    # punto (incluidos los retornos tempranos del filtro de relevancia).
    LANG_NAMES = {
        "ca": "catalan",
        "es": "castellano",
        "ar": "arabe (fusha / arabe estandar, para que lo entienda tambien un hablante de darija marroqui)",
        "ur": "urdu",
    }
    lang_name = LANG_NAMES.get(request.lang, "castellano")

    CANNED_NO_INFO_BY_LANG = {
        "es": "No encuentro esta informacion en los documentos disponibles.",
        "ca": "No trobo aquesta informacio en els documents disponibles.",
        "ar": "\\u0644\\u0627 \\u0623\\u062c\\u062f \\u0647\\u0630\\u0647 \\u0627\\u0644\\u0645\\u0639\\u0644\\u0648\\u0645\\u0629 \\u0641\\u064a \\u0627\\u0644\\u0648\\u062b\\u0627\\u0626\\u0642 \\u0627\\u0644\\u0645\\u062a\\u0627\\u062d\\u0629.",
        "ur": "\\u0645\\u062c\\u06be\\u06d2 \\u062f\\u0633\\u062a\\u06cc\\u0627\\u0628 \\u062f\\u0633\\u062a\\u0627\\u0648\\u06cc\\u0632\\u0627\\u062a \\u0645\\u06cc\\u06ba \\u06cc\\u06c1 \\u0645\\u0639\\u0644\\u0648\\u0645\\u0627\\u062a \\u0646\\u06c1\\u06cc\\u06ba \\u0645\\u0644\\u06cc\\u06ba\\u06d4",
    }
    canned_no_info = CANNED_NO_INFO_BY_LANG.get(request.lang, CANNED_NO_INFO_BY_LANG["es"])

    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + request.message)["embedding"]

    results = collection.query(
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
    context_text = "\\n\\n---\\n\\n".join(context_parts)

    user_prompt = f"IDIOMA DE RESPUESTA: {lang_name}\\n\\nCONTEXTO:\\n{context_text}\\n\\nPREGUNTA DEL PACIENTE:\\n{request.message}"'''

assert old in content, "No se encontro el bloque completo de patient_chat a reordenar"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Funcion patient_chat reordenada correctamente")
