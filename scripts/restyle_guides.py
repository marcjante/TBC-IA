path = "frontend_guides/index.html"
with open(path, encoding="utf-8") as f:
    html = f.read()

# 1. Añadir Google Fonts (Fraunces + Inter + IBM Plex Mono)
old_title = "<title>TBC-AI</title>"
new_title = (
    "<title>TBC-AI</title>\n"
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">'
)
assert old_title in html, "No se encontro el title"
html = html.replace(old_title, new_title)

# 2. Reemplazar paleta de colores (oscura -> calida, coherente con el resto)
old_root = """  :root {
    --bg: #1a1d23;
    --bg-panel: #232730;
    --bg-msg-user: #2d5f7c;
    --bg-msg-bot: #2a2e37;
    --text: #e8e9ec;
    --text-dim: #9a9fa8;
    --accent: #4fa8d8;
    --border: #363c47;
  }"""
new_root = """  :root {
    --bg: #F5F1E8;
    --bg-panel: #FFFEFA;
    --bg-msg-user: #1F4B4C;
    --bg-msg-bot: #EFEADD;
    --text: #1C2420;
    --text-dim: #5B6560;
    --accent: #A8502E;
    --border: #DEDACB;
  }"""
assert old_root in html, "No se encontro el bloque :root"
html = html.replace(old_root, new_root)

# 3. Fuente del cuerpo
old_font = 'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;'
new_font = "font-family: 'Inter', sans-serif;"
assert old_font in html, "No se encontro la fuente del body"
html = html.replace(old_font, new_font)

# 4. Titulo del header con Fraunces
old_h1 = '  header h1 { font-size: 16px; margin: 0; font-weight: 600; }'
new_h1 = "  header h1 { font-family: 'Fraunces', serif; font-size: 19px; margin: 0; font-weight: 600; }"
assert old_h1 in html, "No se encontro header h1"
html = html.replace(old_h1, new_h1)

# 5. Texto blanco en burbujas del usuario (fondo teal oscuro)
old_user = """  .msg.user {
    align-self: flex-end;
    background: var(--bg-msg-user);
  }"""
new_user = """  .msg.user {
    align-self: flex-end;
    background: var(--bg-msg-user);
    color: #F5F1E8;
  }"""
assert old_user in html, "No se encontro .msg.user"
html = html.replace(old_user, new_user)

with open(path, "w", encoding="utf-8") as f:
    f.write(html)

print("Restyling aplicado correctamente")
