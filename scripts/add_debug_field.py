path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old1 = """class ChatRequest(BaseModel):
    message: str
    top_k: int = 8"""
new1 = """class ChatRequest(BaseModel):
    message: str
    top_k: int = 8
    debug: bool = False"""
assert old1 in content, "No se encontro ChatRequest"
content = content.replace(old1, new1, 1)

old2 = """class PatientChatRequest(BaseModel):
    message: str
    lang: str = "es\""""
new2 = """class PatientChatRequest(BaseModel):
    message: str
    lang: str = "es"
    debug: bool = False"""
assert old2 in content, "No se encontro PatientChatRequest"
content = content.replace(old2, new2, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Campo debug anadido a ambos modelos Pydantic")
