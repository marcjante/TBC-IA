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

os.environ["ANONYMIZED_TELEMETRY"] = "False"

app = FastAPI(title="TBC-AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CHAT_MODEL = "qwen2.5:7b"
EMBED_MODEL = "bge-m3"
COLLECTION_NAME = "tbc_docs"
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 300

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "vector_db")
DOCUMENTS_DIR = os.path.join(PROJECT_ROOT, "documents")
GUIDES_DIR = os.path.join(PROJECT_ROOT, "frontend_guides")
PATIENT_DIR = os.path.join(PROJECT_ROOT, "frontend_patient")

chroma_client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

SYSTEM_PROMPT = """Eres un asistente clinico especializado en tuberculosis (TBC).

REGLAS OBLIGATORIAS:
0. Responde SIEMPRE en español, incluso si los documentos fuente estan en ingles u otro idioma. Traduce terminologia tecnica al espanol cuando exista un termino equivalente reconocido.
1. Responde EXCLUSIVAMENTE usando la informacion contenida en el CONTEXTO proporcionado abajo.
2. Si el contexto no contiene informacion suficiente para responder, di textualmente: "No encuentro esta informacion en los documentos disponibles."
3. No inventes datos, cifras, ni recomendaciones que no esten en el contexto.
4. Cita siempre la fuente y pagina de cada afirmacion, usando el formato: (Fuente: {source}, p.{page}).
5. Si distintas fuentes del contexto se contradicen entre si, indicalo explicitamente y explica la discrepancia en vez de elegir una sin mas.
6. Separa claramente los datos/evidencia de tu interpretacion cuando la haya.
7. Si usas la frase "No encuentro esta informacion en los documentos disponibles", esa debe ser tu UNICA respuesta. No añadas explicaciones, aproximaciones ni conocimiento general a continuacion.
"""


class ChatRequest(BaseModel):
    message: str
    top_k: int = 8


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def chunk_id(source_file, page_num, chunk_index):
    raw = f"{source_file}|{page_num}|{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def index_single_pdf(pdf_path, category, fname):
    doc = fitz.open(pdf_path)
    total_chunks = 0

    for i, page in enumerate(doc):
        page_num = i + 1
        text = page.get_text().strip()
        if not text:
            continue

        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            cid = chunk_id(f"{category}/{fname}", page_num, idx)
            embedding = ollama.embeddings(model=EMBED_MODEL, prompt=chunk)["embedding"]

            collection.upsert(
                ids=[cid],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "source": fname,
                    "category": category,
                    "page": page_num,
                }],
            )
            total_chunks += 1

    doc.close()
    return total_chunks


@app.get("/api/health")
def health():
    try:
        ollama.list()
        doc_count = collection.count()
        return {"status": "ok", "model": CHAT_MODEL, "documentos_indexados": doc_count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/chat")
def chat(request: ChatRequest):
    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt=request.message)["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=request.top_k,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []

    if not fragments:
        return {
            "response": "No encuentro esta informacion en los documentos disponibles.",
            "sources": [],
        }

    context_parts = []
    sources_used = []
    for frag, meta in zip(fragments, metadatas):
        context_parts.append(
            "[Fuente: " + meta["source"] + ", categoria: " + meta["category"] + ", pagina: " + str(meta["page"]) + "]\n" + frag
        )
        sources_used.append({
            "source": meta["source"],
            "category": meta["category"],
            "page": meta["page"],
        })

    context_text = "\n\n---\n\n".join(context_parts)
    user_prompt = "CONTEXTO:\n" + context_text + "\n\nPREGUNTA DEL USUARIO:\n" + request.message

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "temperature": 0.1,
            "top_p": 0.9,
        },
    )

    return {
        "response": response["message"]["content"],
        "sources": sources_used,
    }


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), category: str = Form("sin_categoria")):
    if not file.filename.lower().endswith(".pdf"):
        return {"status": "error", "detail": "Solo se aceptan archivos PDF por ahora."}

    category_dir = os.path.join(DOCUMENTS_DIR, category)
    os.makedirs(category_dir, exist_ok=True)

    dest_path = os.path.join(category_dir, file.filename)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        chunks_created = index_single_pdf(dest_path, category, file.filename)
    except Exception as e:
        return {"status": "error", "detail": f"Archivo guardado pero fallo la indexacion: {str(e)}"}

    return {
        "status": "ok",
        "filename": file.filename,
        "category": category,
        "chunks_indexed": chunks_created,
        "total_documentos_indexados": collection.count(),
    }


@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="ca">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TBC · Panell local</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --paper: #F5F1E8;
    --ink: #1C2420;
    --ink-soft: #5B6560;
    --teal: #1F4B4C;
    --teal-bright: #3E8E89;
    --rust: #A8502E;
    --line: #DEDACB;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 64px 24px 40px;
  }
  .eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--teal-bright);
    margin-bottom: 14px;
  }
  h1 {
    font-family: 'Fraunces', serif;
    font-optical-sizing: auto;
    font-weight: 600;
    font-size: clamp(36px, 6vw, 56px);
    margin: 0;
    color: var(--ink);
    text-align: center;
  }
  .sub {
    color: var(--ink-soft);
    font-size: 15px;
    max-width: 440px;
    text-align: center;
    margin: 14px 0 0;
    line-height: 1.5;
  }
  .wave {
    width: 100%;
    max-width: 560px;
    height: 40px;
    margin: 40px 0 44px;
  }
  .wave path {
    fill: none;
    stroke: var(--teal-bright);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-dasharray: 600;
    stroke-dashoffset: 600;
    animation: draw 3.2s ease-in-out infinite alternate;
    opacity: 0.55;
  }
  @keyframes draw {
    to { stroke-dashoffset: 0; }
  }
  .cards {
    display: flex;
    gap: 22px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 880px;
    width: 100%;
  }
  .card {
    flex: 1 1 320px;
    max-width: 380px;
    background: #FFFEFA;
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 30px 28px 26px;
    text-decoration: none;
    color: inherit;
    position: relative;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  }
  .card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 28px rgba(28,36,32,0.09);
    border-color: var(--teal-bright);
  }
  .tag {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    padding: 4px 10px;
    border-radius: 3px;
    margin-bottom: 16px;
  }
  .tag.patient { background: rgba(31,75,76,0.1); color: var(--teal); }
  .tag.clinic { background: rgba(168,80,46,0.1); color: var(--rust); }
  .card h2 {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 23px;
    margin: 0 0 10px;
  }
  .card p {
    font-size: 13.5px;
    color: var(--ink-soft);
    line-height: 1.55;
    margin: 0 0 20px;
  }
  .status {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--ink-soft);
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--teal-bright);
    flex-shrink: 0;
  }
  footer {
    margin-top: 56px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--ink-soft);
    text-align: center;
    letter-spacing: 0.02em;
  }
  @media (max-width: 480px) {
    body { padding: 44px 18px 32px; }
  }
</style>
</head>
<body>
  <div class="eyebrow">Panell local · Tuberculosi</div>
  <h1>Consulta &amp; guies</h1>
  <p class="sub">Dues eines, un sol servidor. Tot funciona al teu ordinador, sense connexio a internet ni dades que en surtin.</p>

  <svg class="wave" viewBox="0 0 560 40" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,20 L120,20 L136,6 L152,34 L168,20 L200,20 L216,12 L232,28 L248,20 L560,20" />
  </svg>

  <div class="cards">
    <a class="card" href="/patient/">
      <span class="tag patient">Pacients</span>
      <h2>Seguiment TBC · ITL</h2>
      <p>Xat de triatge amb pacients en tractament, historial de missatges i panell professional de seguiment.</p>
      <div class="status"><span class="dot"></span>Firestore · en linia</div>
    </a>
    <a class="card" href="/guides/">
      <span class="tag clinic">Clinic</span>
      <h2>TBC-AI</h2>
      <p>Assistent sobre guies cliniques de l'OMS, CDC i ECDC, amb cita de font i pagina en cada resposta.</p>
      <div class="status"><span class="dot"></span>Ollama · qwen2.5:7b</div>
    </a>
  </div>

  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
</body>
</html>
"""


app.mount("/guides", StaticFiles(directory=GUIDES_DIR, html=True), name="guides")
app.mount("/patient", StaticFiles(directory=PATIENT_DIR, html=True), name="patient")
