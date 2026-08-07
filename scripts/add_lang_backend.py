path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '    lang_name = "catalan" if request.lang == "ca" else "castellano"'

new = '''    LANG_NAMES = {
        "ca": "catalan",
        "es": "castellano",
        "ar": "arabe (fusha / arabe estandar, para que lo entienda tambien un hablante de darija marroqui)",
        "ur": "urdu",
    }
    lang_name = LANG_NAMES.get(request.lang, "castellano")'''

assert old in content, "No se encontro la linea de lang_name"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("lang_name ampliado a 4 idiomas")
