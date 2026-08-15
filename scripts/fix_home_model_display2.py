path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
</body>
</html>
"""'''

new = '''  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
</body>
</html>
"""
    return html.replace("{CHAT_MODEL_PLACEHOLDER}", CHAT_MODEL)'''

assert old in content, "No se encontro el cierre exacto de home()"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Paso 2: home() ahora devuelve el modelo real")
