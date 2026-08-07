path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    lines = f.readlines()

# Linea 289 (indice 288) es la del endpoint /api/chat, que NO tiene campo lang.
target_idx = 288
old_line = 'has_keyword = is_tb_related(request.message) or request.lang in ("ar", "ur")'
new_line = 'has_keyword = is_tb_related(request.message)'

assert old_line in lines[target_idx], f"La linea {target_idx+1} no coincide con lo esperado: {lines[target_idx]}"

indent = lines[target_idx][:len(lines[target_idx]) - len(lines[target_idx].lstrip())]
lines[target_idx] = indent + new_line + "\n"

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Linea 289 corregida (endpoint /api/chat, sin campo lang)")
