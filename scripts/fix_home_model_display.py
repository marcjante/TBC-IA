path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = 'def home():\n    return """'
new = 'def home():\n    html = """'

assert old in content, "No se encontro el inicio de home()"
content = content.replace(old, new, 1)

old_end_marker = '<div class="status"><span class="dot"></span>Ollama · qwen2.5:7b</div>'
new_end_marker = '<div class="status"><span class="dot"></span>Ollama · {CHAT_MODEL_PLACEHOLDER}</div>'

assert old_end_marker in content, "No se encontro la linea de qwen2.5"
content = content.replace(old_end_marker, new_end_marker)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Paso 1: placeholder insertado, pendiente cerrar la funcion")
