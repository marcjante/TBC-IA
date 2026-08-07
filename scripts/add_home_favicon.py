path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

favicon_tag = (
    '<link rel="icon" href="data:image/svg+xml,'
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
    "%3Crect width='100' height='100' rx='20' fill='%231F4B4C'/%3E"
    "%3Cpath d='M10,50 L35,50 L42,30 L50,70 L58,50 L90,50' "
    "stroke='%233E8E89' stroke-width='7' fill='none' stroke-linecap='round'/%3E"
    '%3C/svg%3E">'
)

old = "<title>TBC \u00b7 Panell local</title>"
assert old in content, "No se encontro el title exacto"

if "rel=\"icon\"" not in content:
    content = content.replace(old, old + "\n" + favicon_tag)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Favicon insertado en backend/main.py")
else:
    print("El favicon ya estaba presente, no se hizo ningun cambio")
