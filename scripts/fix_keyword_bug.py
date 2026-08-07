path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    def is_tb_related(text):
        normalized = text.lower()
        return any(kw in normalized for kw in TB_KEYWORDS)'''

new = '''    def is_tb_related(text):
        normalized = text.lower()
        normalized = normalized.replace("?", " ").replace("!", " ").replace(".", " ").replace(",", " ")
        normalized = " " + normalized + " "
        return any((" " + kw if not kw.endswith(" ") else kw) in normalized for kw in TB_KEYWORDS) or any(kw.strip() in normalized for kw in TB_KEYWORDS)'''

assert old in content, "No se encontro la funcion is_tb_related"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Bug de palabras clave con espacio final corregido")
