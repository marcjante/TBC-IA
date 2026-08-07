path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    lines = f.readlines()

# Las lineas 443, 447, 450 (indice 442, 446, 449) son las devoluciones fijas
# dentro de patient_chat que hay que traducir segun el idioma.
target_line_numbers_1indexed = [443, 447, 450]
old_snippet = '        return {"response": "No encuentro esta informacion en los documentos disponibles."}'
new_snippet = '        return {"response": canned_no_info}'

changed = 0
for ln in target_line_numbers_1indexed:
    idx = ln - 1
    if idx < len(lines) and old_snippet.strip() in lines[idx].strip():
        # preservar la indentacion original de cada linea
        indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
        lines[idx] = indent + 'return {"response": canned_no_info}\n'
        changed += 1

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"Lineas reemplazadas: {changed} de {len(target_line_numbers_1indexed)}")
