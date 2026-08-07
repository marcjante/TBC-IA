path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

NEW_KEYWORDS = [
    # Muy comunes, sorprendentemente ausentes
    "dolor", "vomit", "nausea", "pica", "borros",
    # Seguimiento / pruebas coloquial
    "visita", "analitica", "termin", "resultado",
    # Edad / estado
    "mayor", "defensas",
    # Medicacion / tratamiento
    "interaccion", "cura", "curar",
    # Embarazo
    "parto",
    # Prevencion / aislamiento (stem mas amplio que "aislar")
    "aisla",
    # Emocional / social
    "apoyo", "despid", "confidencial", "rechaz", "pronostico",
]

start_marker = "TB_KEYWORDS = ["
end_marker = "\n]"

start_idx = content.find(start_marker)
assert start_idx != -1, "No se encontro TB_KEYWORDS"
end_idx = content.find(end_marker, start_idx)
assert end_idx != -1, "No se encontro el cierre de TB_KEYWORDS"

existing_block = content[start_idx:end_idx]

added = 0
insertion_lines = []
for kw in NEW_KEYWORDS:
    token = f'"{kw}"'
    if token not in existing_block:
        insertion_lines.append(f'    {token},')
        added += 1

if insertion_lines:
    insertion_text = "\n" + "\n".join(insertion_lines)
    content = content[:end_idx] + insertion_text + content[end_idx:]

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Palabras clave nuevas añadidas: {added}")
