path = "frontend_patient/index.html"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '<script src="kb/buscador.js"></script>\n'
assert old in content, "No se encontro la linea exacta"
content = content.replace(old, "")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Linea de carga de kb/buscador.js eliminada de index.html")
