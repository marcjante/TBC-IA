path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old_imports = """import re
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import ollama
import chromadb
import os
import hashlib
import shutil
import fitz

os.environ["ANONYMIZED_TELEMETRY"] = "False\""""

new_imports = """import re
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import ollama
import chromadb
import os
import hashlib
import shutil
import fitz
from dotenv import load_dotenv

load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "False\""""

assert old_imports in content, "No se encontro el bloque de imports"
content = content.replace(old_imports, new_imports)

old_models = 'CHAT_MODEL = "llama3.1:8b"\nEMBED_MODEL = "bge-m3"'
new_models = 'CHAT_MODEL = os.environ.get("TBC_CHAT_MODEL", "llama3.1:8b")\nEMBED_MODEL = os.environ.get("TBC_EMBED_MODEL", "bge-m3")'

assert old_models in content, "No se encontro el bloque de modelos"
content = content.replace(old_models, new_models)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Modelo desacoplado a variables de entorno")
