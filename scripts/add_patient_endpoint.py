path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

anchor = '@app.get("/", response_class=HTMLResponse)'
assert anchor in content, "No se encontro el anchor de la ruta /"

new_code = '''PATIENT_SYSTEM_PROMPT = """Eres un asistente que ayuda a pacientes en tratamiento de tuberculosis a entender su enfermedad.
Hablas con el propio paciente, no con un profesional sanitario.

REGLAS OBLIGATORIAS:
0. Responde en el idioma indicado (variable de idioma), con frases cortas y palabras sencillas, como hablarias con alguien sin conocimientos medicos. Evita jerga clinica; si usas un termino tecnico, explicalo en la misma frase con palabras normales.
1. Responde EXCLUSIVAMENTE usando la informacion contenida en el CONTEXTO proporcionado abajo. Tienes PROHIBIDO usar conocimiento general o entrenamiento previo para completar lo que falte en el contexto, incluso si ese conocimiento es correcto.
2. Si el contexto no contiene informacion suficiente para responder, tu respuesta COMPLETA debe ser, sin nada mas antes ni despues: "No encuentro esta informacion en los documentos disponibles."
3. No inventes datos, dosis, ni recomendaciones que no esten en el contexto. Nunca ofrezcas informacion general como alternativa: usa la frase fija de la regla 2.
4. No des consejos que sustituyan a un profesional sanitario. Si la pregunta suena a sintoma, urgencia o duda sobre su propia medicacion, recuerda amablemente que consulte a su equipo de TBC ademas de responder lo que digan los documentos.
5. Tono calido y cercano, nunca alarmista. No repitas la pregunta del paciente.
6. No cites nombres de archivos PDF ni paginas al paciente: eso es para profesionales. Si necesitas referenciar el origen, di simplemente "segun las guias clinicas".
"""


class PatientChatRequest(BaseModel):
    message: str
    lang: str = "es"


@app.post("/api/patient-chat")
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
        return {"response": "No encuentro esta informacion en los documentos disponibles."}

    if has_keyword:
        if distances[0] > LOOSE_DISTANCE_THRESHOLD:
            return {"response": "No encuentro esta informacion en los documentos disponibles."}
    else:
        if distances[0] > STRICT_DISTANCE_THRESHOLD:
            return {"response": "No encuentro esta informacion en los documentos disponibles."}

    context_parts = [frag for frag in fragments]
    context_text = "\\n\\n---\\n\\n".join(context_parts)

    lang_name = "catalan" if request.lang == "ca" else "castellano"
    user_prompt = f"IDIOMA DE RESPUESTA: {lang_name}\\n\\nCONTEXTO:\\n{context_text}\\n\\nPREGUNTA DEL PACIENTE:\\n{request.message}"

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": PATIENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        options={"temperature": 0.1, "top_p": 0.9},
    )

    final_response = response["message"]["content"]
    normalized_check = final_response.lower()
    leaked = any(pat in normalized_check for pat in [
        "sin embargo, puedo ofrecerte", "informacion general sobre",
        "segun mi conocimiento", "de manera general,",
    ])
    if leaked:
        final_response = "No encuentro esta informacion en los documentos disponibles."

    return {"response": final_response}


''' + anchor

content = content.replace(anchor, new_code)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Endpoint /api/patient-chat anadido correctamente")
