import re

path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

start_marker = "    TB_KEYWORDS = ["
end_marker = '        return any((" " + kw if not kw.endswith(" ") else kw) in normalized for kw in TB_KEYWORDS) or any(kw.strip() in normalized for kw in TB_KEYWORDS)\n'

start_idx = content.find(start_marker)
assert start_idx != -1, "No se encontro el inicio del bloque"

end_idx = content.find(end_marker, start_idx)
assert end_idx != -1, "No se encontro el final del bloque"
end_idx += len(end_marker)

indented_block = content[start_idx:end_idx]

dedented_block = "\n".join(
    line[4:] if line.startswith("    ") else line
    for line in indented_block.split("\n")
)

content = content[:start_idx] + content[end_idx:]

anchor = "collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)\n"
assert anchor in content, "No se encontro el anchor de collection"
content = content.replace(anchor, anchor + "\n" + dedented_block + "\n", 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("TB_KEYWORDS e is_tb_related movidos a nivel de modulo")
