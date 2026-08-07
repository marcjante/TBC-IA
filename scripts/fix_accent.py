path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = 'no_info_phrase = "No encuentro esta informacion en los documentos disponibles"'
new = 'no_info_phrase = "No encuentro esta informaci"'

assert old in content, "No se encontro la linea a corregir"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Correccion de acento aplicada")
