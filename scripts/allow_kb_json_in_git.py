path = ".gitignore"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = "# Documentos clinicos - no versionar\ndocuments/"
new = """# Documentos clinicos - no versionar (excepto la Knowledge Base JSON,
# que no son PDF con copyright sino fichas propias con citas bibliograficas)
documents/*
!documents/05_ClinicalKB_JSON/
!documents/05_ClinicalKB_JSON/**"""

assert old in content, "No se encontro el bloque exacto de documents/"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Excepcion anadida para documents/05_ClinicalKB_JSON")
