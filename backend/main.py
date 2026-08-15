"""
TBC-AI - backend/main.py

Backend FastAPI. Tras la FASE 7 de la auditoria (modularizacion), este
archivo contiene solo: configuracion de la app, modelos Pydantic, y la
orquestacion de cada endpoint (llamando a las funciones de safety.py,
prompts.py, languages.py, rag.py y llm.py). La logica de negocio en si
vive en esos modulos.

Sigue siendo UN SOLO proceso FastAPI (sin microservicios), tal como pedia
la arquitectura objetivo de la auditoria.
"""

import re
import os
import shutil

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import ollama

from backend.config import CHAT_MODEL, DOCUMENTS_DIR, GUIDES_DIR, PATIENT_DIR, collection
from backend.safety import is_tb_related, detect_generic_knowledge_leak
from backend.prompts import SYSTEM_PROMPT, PATIENT_SYSTEM_PROMPT
from backend.languages import resolve_lang_name, resolve_canned_no_info
from backend.rag import retrieve, is_relevant, index_single_pdf
from backend.llm import generate_response

app = FastAPI(title="TBC-AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    top_k: int = 8
    debug: bool = False


class PatientChatRequest(BaseModel):
    message: str
    lang: str = "es"
    debug: bool = False


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
    fragments, metadatas, distances = retrieve(request.message, request.top_k)
    has_keyword = is_tb_related(request.message)

    if not is_relevant(fragments, distances, has_keyword):
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

    final_response = generate_response(SYSTEM_PROMPT, user_prompt)

    no_info_phrase = "No encuentro esta informaci"
    CANNED_NO_INFO = "No encuentro esta informacion en los documentos disponibles."

    leaked = detect_generic_knowledge_leak(final_response)

    # Se busca la frase fija en cualquier parte de la respuesta, no solo al
    # principio: el modelo a veces la antepone con texto propio (ej. "La
    # respuesta es: No encuentro..."), lo que antes hacia que no se vaciaran
    # las fuentes aunque el propio modelo diga que no sabe la respuesta.
    if no_info_phrase in final_response:
        final_response = CANNED_NO_INFO
        sources_used = []
    elif leaked:
        final_response = CANNED_NO_INFO
        sources_used = []

    result = {
        "response": final_response,
        "sources": sources_used,
    }
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": request.top_k,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fragments_retrieved": len(fragments),
        }
    return result


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


@app.post("/api/patient-chat")
def patient_chat(request: PatientChatRequest):
    lang_name = resolve_lang_name(request.lang)
    canned_no_info = resolve_canned_no_info(request.lang)

    fragments, metadatas, distances = retrieve(request.message, 8)

    # La lista TB_KEYWORDS solo cubre espanol: en arabe/urdu nunca habria
    # coincidencia, lo que forzaria siempre el umbral estricto (480) aunque
    # la pregunta sea legitima. Como esta app esta dedicada integramente a
    # tuberculosis, tratamos estos dos idiomas como "dentro de dominio" por
    # defecto y usamos el umbral permisivo (750).
    has_keyword = is_tb_related(request.message) or request.lang in ("ar", "ur")

    if not is_relevant(fragments, distances, has_keyword):
        return {"response": canned_no_info}

    context_parts = [frag for frag in fragments]
    context_text = "\n\n---\n\n".join(context_parts)

    user_prompt = f"IDIOMA DE RESPUESTA: {lang_name}\n\nCONTEXTO:\n{context_text}\n\nPREGUNTA DEL PACIENTE:\n{request.message}"

    final_response = generate_response(PATIENT_SYSTEM_PROMPT, user_prompt)

    normalized_check = final_response.lower()
    for a, b in [("\u00e1", "a"), ("\u00e9", "e"), ("\u00ed", "i"), ("\u00f3", "o"), ("\u00fa", "u")]:
        normalized_check = normalized_check.replace(a, b)

    CANNED_NO_INFO_PATIENT = "No encuentro esta informacion en los documentos disponibles."

    # Si el modelo expresa "no lo se" con sus propias palabras (con o sin
    # rodeos tipo "lo siento"), lo normalizamos a la frase fija, en vez de
    # dejar pasar variantes que no coinciden exactamente y contaminan las
    # estadisticas de "con respuesta / sin cobertura".
    no_info_variants = [
        "no encuentro esta informacion", "no encuentro informacion",
        "no tengo esta informacion", "no tengo informacion",
        "no dispongo de esta informacion", "no dispongo de informacion",
        "no cuento con esta informacion", "no cuento con informacion",
    ]
    said_no_info = any(v in normalized_check for v in no_info_variants)

    leaked = detect_generic_knowledge_leak(final_response)

    if said_no_info or leaked:
        final_response = CANNED_NO_INFO_PATIENT

    # Elimina menciones a nombres de archivo, URLs o citas de fuente que el
    # modelo pueda colar pese a la instruccion del prompt de no mencionarlas
    # al paciente (regla 6 del PATIENT_SYSTEM_PROMPT).
    final_response = re.sub(r"\(Fuente:.*?\)", "", final_response, flags=re.IGNORECASE | re.DOTALL)
    final_response = re.sub(r"https?://\S+", "", final_response)
    final_response = re.sub(r"\S+\.pdf", "", final_response, flags=re.IGNORECASE)
    final_response = re.sub(r"\s{2,}", " ", final_response).strip()

    result = {"response": final_response}
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": 8,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
        }
    return result


@app.get("/", response_class=HTMLResponse)
def home():
    html = """
<!DOCTYPE html>
<html lang="ca">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TBC · Panell local</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%231F4B4C'/%3E%3Cpath d='M10,50 L35,50 L42,30 L50,70 L58,50 L90,50' stroke='%233E8E89' stroke-width='7' fill='none' stroke-linecap='round'/%3E%3C/svg%3E">
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
      <div class="status"><span class="dot"></span>Ollama · {CHAT_MODEL_PLACEHOLDER}</div>
    </a>
  </div>

  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
</body>
</html>
"""
    return html.replace("{CHAT_MODEL_PLACEHOLDER}", CHAT_MODEL)


app.mount("/guides", StaticFiles(directory=GUIDES_DIR, html=True), name="guides")
app.mount("/patient", StaticFiles(directory=PATIENT_DIR, html=True), name="patient")
