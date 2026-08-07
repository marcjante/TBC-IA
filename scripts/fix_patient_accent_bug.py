path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    final_response = response["message"]["content"]
    normalized_check = final_response.lower()

    CANNED_NO_INFO_PATIENT = "No encuentro esta informacion en los documentos disponibles."'''

new = '''    final_response = response["message"]["content"]
    normalized_check = final_response.lower()
    for a, b in [("\\u00e1", "a"), ("\\u00e9", "e"), ("\\u00ed", "i"), ("\\u00f3", "o"), ("\\u00fa", "u")]:
        normalized_check = normalized_check.replace(a, b)

    CANNED_NO_INFO_PATIENT = "No encuentro esta informacion en los documentos disponibles."'''

assert old in content, "No se encontro el bloque a corregir"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Bug de acentos corregido en patient_chat")
