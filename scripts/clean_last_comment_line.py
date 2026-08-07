path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    LOOSE_DISTANCE_THRESHOLD = 750


    # La lista TB_KEYWORDS solo cubre espanol: en arabe/urdu nunca habria
    has_keyword = is_tb_related(request.message)'''

new = '''    LOOSE_DISTANCE_THRESHOLD = 750

    has_keyword = is_tb_related(request.message)'''

assert old in content, "No se encontro el bloque exacto a limpiar"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Linea huerfana eliminada")
