path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    lines = f.readlines()

# Bloque de comentario sobrante justo antes de la linea 289 (indice 284-287)
target_range = range(284, 288)  # lineas 285-288 (0-indexed)
expected_starts = [
    "    # coincidencia",
    "    # la pregunta sea legitima",
    "    # tuberculosis, tratamos",
    "    # defecto y usamos",
]

# Verificamos que efectivamente son esas 4 lineas antes de borrar
ok = all(lines[i].strip().startswith(expected_starts[j].strip())
         for j, i in enumerate(target_range))
assert ok, "Las lineas no coinciden con lo esperado, abortando por seguridad"

new_lines = [line for i, line in enumerate(lines) if i not in target_range]

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Comentario sobrante eliminado (4 lineas)")
