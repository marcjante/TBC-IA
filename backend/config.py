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

SOTA_ENGINE_URL = "http://127.0.0.1:8000"
SOTA_ENGINE_API_KEY = os.environ.get("SOTA_ENGINE_API_KEY", "tbc_ia_secret_v7")
