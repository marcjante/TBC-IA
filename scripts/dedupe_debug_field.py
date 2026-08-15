path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old1 = "    debug: bool = False\n    debug: bool = False\n"
new1 = "    debug: bool = False\n"

count = content.count(old1)
content = content.replace(old1, new1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Duplicados eliminados: {count}")
