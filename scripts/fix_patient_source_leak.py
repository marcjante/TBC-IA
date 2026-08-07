import re

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
        final_response = "No encuentro esta informacion en los documentos disponibles."

    return {"response": final_response}'''

new = '''    final_response = response["message"]["content"]
    normalized_check = final_response.lower()
    leaked = any(pat in normalized_check for pat in [
        "sin embargo, puedo ofrecerte", "informacion general sobre",
        "segun mi conocimiento", "de manera general,",
    ])
    if leaked:
        final_response = "No encuentro esta informacion en los documentos disponibles."

    # Elimina menciones a nombres de archivo, URLs o citas de fuente que el
    # modelo pueda colar pese a la instruccion del prompt de no mencionarlas
    # al paciente (regla 6 del PATIENT_SYSTEM_PROMPT).
    final_response = re.sub(r"\\(Fuente:.*?\\)", "", final_response, flags=re.IGNORECASE | re.DOTALL)
    final_response = re.sub(r"https?://\\S+", "", final_response)
    final_response = re.sub(r"\\S+\\.pdf", "", final_response, flags=re.IGNORECASE)
    final_response = re.sub(r"\\s{2,}", " ", final_response).strip()

    return {"response": final_response}'''

assert old in content, "No se encontro el bloque exacto de patient_chat a reemplazar"
content = content.replace(old, new)

if "import re" not in content.split("\\n\\n")[0]:
    content = content.replace("import requests\\n", "import requests\\nimport re\\n", 1) if "import requests" in content else content

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Guard de fuga de fuentes en patient_chat aplicado")
