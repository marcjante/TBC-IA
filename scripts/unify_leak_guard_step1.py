path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

anchor = "def is_tb_related(text):"
assert anchor in content, "No se encontro is_tb_related"

shared_function = '''# Patrones que indican que el modelo esta "rellenando" con conocimiento
# general en vez de limitarse al contexto recuperado (fuga de conocimiento).
# Union de los patrones detectados historicamente en ambos endpoints de chat;
# compartida para que un patron nuevo anadido aqui proteja a los dos a la vez.
LEAK_PATTERNS = [
    "no contiene informacion especifica",
    "sin embargo, puedo ofrecerte",
    "puedo ofrecerte informacion general",
    "puedo ofrecerte",
    "puedo darte informacion general",
    "informacion general sobre",
    "de manera general,",
    "por lo general,",
    "segun mi conocimiento",
    "el texto proporcionado no",
    "el contexto no contiene",
    "no se menciona explicitamente",
]


def normalize_accents(text):
    t = text.lower()
    for a, b in [("\\u00e1", "a"), ("\\u00e9", "e"), ("\\u00ed", "i"), ("\\u00f3", "o"), ("\\u00fa", "u")]:
        t = t.replace(a, b)
    return t


def detect_generic_knowledge_leak(response_text):
    normalized = normalize_accents(response_text)
    return any(normalize_accents(pat) in normalized for pat in LEAK_PATTERNS)


'''

content = content.replace(anchor, shared_function + anchor, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Funcion compartida detect_generic_knowledge_leak anadida")
