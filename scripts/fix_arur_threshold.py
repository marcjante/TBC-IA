path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = "    has_keyword = is_tb_related(request.message)"

new = '''    # La lista TB_KEYWORDS solo cubre espanol: en arabe/urdu nunca habria
    # coincidencia, lo que forzaria siempre el umbral estricto (480) aunque
    # la pregunta sea legitima. Como esta app esta dedicada integramente a
    # tuberculosis, tratamos estos dos idiomas como "dentro de dominio" por
    # defecto y usamos el umbral permisivo (750).
    has_keyword = is_tb_related(request.message) or request.lang in ("ar", "ur")'''

assert old in content, "No se encontro la linea has_keyword en patient_chat"
# Solo reemplazar dentro del cuerpo de patient_chat (unica funcion que la usa igual)
content = content.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Umbral permisivo aplicado para ar/ur")
