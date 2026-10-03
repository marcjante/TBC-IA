"""
TBC-AI - backend/config.py

Configuracion central del backend: variables de entorno, constantes y el
cliente de ChromaDB (singleton compartido por rag.py y main.py).

FASE 7 de la auditoria: extraido de main.py sin cambiar ningun valor por
defecto ni comportamiento.
"""

import os
import chromadb
from dotenv import load_dotenv

load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "False"

CHAT_MODEL = os.environ.get("TBC_CHAT_MODEL", "llama3.1:8b")
EMBED_MODEL = os.environ.get("TBC_EMBED_MODEL", "bge-m3")
COLLECTION_NAME = "tbc_docs"
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 300
MIN_ALNUM_CHARS = 40

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "vector_db")
DOCUMENTS_DIR = os.path.join(PROJECT_ROOT, "documents")
GUIDES_DIR = os.path.join(PROJECT_ROOT, "frontend_guides")
PATIENT_DIR = os.path.join(PROJECT_ROOT, "frontend_patient")

chroma_client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

SOTA_ENGINE_URL = "http://127.0.0.1:8003"

# Secretos (revision de seguridad, octubre 2026): sin valores por defecto en
# el codigo. La clave antigua "tbc_ia_secret_v7" quedo publicada en git y se
# ha rotado. Si falta TBC_API_KEY el backend no arranca (fallo explicito en
# vez de quedar "protegido" con una clave conocida).
SOTA_ENGINE_API_KEY = os.environ["TBC_API_KEY"]

# Token de administrador para /api/upload. Si no esta definido, la subida de
# documentos queda desactivada (la ingesta sigue disponible por script).
ADMIN_TOKEN = os.environ.get("TBC_ADMIN_TOKEN", "")

# Origenes y hosts permitidos: todos los servicios son locales. Restringir
# CORS y la cabecera Host evita que una web cualquiera abierta en el
# navegador (o un ataque de DNS rebinding) use la API.
ALLOWED_ORIGINS = [
    "http://127.0.0.1:8001", "http://localhost:8001",
    "http://127.0.0.1:8090", "http://localhost:8090",
]
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Desarrollo: solo con TBC_DEV_MODE=1 el chat de pacientes puede devolver
# debug_info (nunca en uso real).
DEV_MODE = os.environ.get("TBC_DEV_MODE") == "1"
