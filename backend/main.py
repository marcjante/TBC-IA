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
import json
import shutil
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from pydantic import BaseModel
import ollama
import fitz

from backend.config import CHAT_MODEL, DOCUMENTS_DIR, GUIDES_DIR, PATIENT_DIR, PROJECT_ROOT, collection
from backend.safety import is_tb_related, detect_generic_knowledge_leak, detect_model_refusal, detect_no_info_statement
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


class HistoryTurn(BaseModel):
    role: str  # "user" o "bot"
    content: str


class ChatRequest(BaseModel):
    message: str
    top_k: int = 8
    debug: bool = False
    history: list[HistoryTurn] = []


class PatientChatRequest(BaseModel):
    message: str
    lang: str = "es"
    debug: bool = False
    history: list[HistoryTurn] = []


@app.get("/api/health")
def health():
    try:
        ollama.list()
        doc_count = collection.count()
        return {"status": "ok", "model": CHAT_MODEL, "documentos_indexados": doc_count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


MAX_HISTORY_TURNS = 2  # ultimo intercambio (1 pregunta + 1 respuesta), no todo el historial
MAX_HISTORY_CHARS = 400  # recorte defensivo por mensaje, para no desbordar la ventana de contexto del modelo


def build_retrieval_query(message, history):
    """Si el mensaje actual es muy corto (probable pregunta de seguimiento,
    ej. '¿y en niños?'), se combina con la ultima pregunta del usuario para
    mejorar la busqueda vectorial, que de otro modo tendria muy poca
    informacion sobre la que buscar. Si el mensaje ya es largo/autonomo, se
    usa tal cual, para que cambiar de tema de golpe no arrastre resultados
    del tema anterior."""
    if len(message.strip()) >= 40 or not history:
        return message
    previous_user_msgs = [h.content for h in history if h.role == "user"]
    if not previous_user_msgs:
        return message
    return previous_user_msgs[-1] + " " + message


def build_history_block(history):
    """Construye un bloque de texto con el ultimo intercambio (pregunta +
    respuesta), recortado, para dar continuidad a la conversacion sin
    arriesgar desbordar la ventana de contexto del modelo (4096 tokens,
    ya ajustada por los propios fragmentos del RAG)."""
    if not history:
        return ""
    recent = history[-MAX_HISTORY_TURNS:]
    lines = []
    for turn in recent:
        role_label = "Usuario" if turn.role == "user" else "Asistente"
        content = turn.content[:MAX_HISTORY_CHARS]
        lines.append(f"{role_label}: {content}")
    return "HISTORIAL RECIENTE (para dar continuidad a la conversacion, no es una fuente de informacion clinica):\n" + "\n".join(lines) + "\n\n"


USAGE_LOG_PATH = os.path.join(PROJECT_ROOT, "usage_patterns.jsonl")


def log_usage_pattern(endpoint, coverage, question=None, lang=None):
    """Registro ligero de patrones de uso real, para poder revisar despues
    (con scripts/analyze_usage_patterns.py) que preguntas se repiten sin
    buena cobertura documental y decidir que ampliar en la base de
    conocimiento. NUNCA debe romper la respuesta al usuario si falla: se
    envuelve en try/except y se ignora cualquier error silenciosamente.

    Decision de privacidad (agosto 2026): en /api/chat (guias, uso
    profesional) se guarda el texto completo de la pregunta, porque el
    riesgo de que contenga datos personales de pacientes es bajo y el
    texto es lo que hace util el registro para detectar huecos concretos.
    En /api/patient-chat NO se guarda el texto de la pregunta (los
    pacientes a veces escriben detalles personales sin querer), solo la
    clasificacion de cobertura y el idioma."""
    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "coverage": coverage,
        }
        if question is not None:
            entry["question"] = question
        if lang is not None:
            entry["lang"] = lang
        with open(USAGE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


@app.post("/api/chat")
def chat(request: ChatRequest):
    retrieval_query = build_retrieval_query(request.message, request.history)
    fragments, metadatas, distances = retrieve(retrieval_query, request.top_k)
    has_keyword = is_tb_related(request.message)

    if not is_relevant(fragments, distances, has_keyword):
        log_usage_pattern("/api/chat", "sin_cobertura", question=request.message)
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
            "text": frag,
        })

    context_text = "\n\n---\n\n".join(context_parts)
    history_block = build_history_block(request.history)
    user_prompt = history_block + "CONTEXTO:\n" + context_text + "\n\nPREGUNTA DEL USUARIO:\n" + request.message

    final_response = generate_response(SYSTEM_PROMPT, user_prompt)

    CANNED_NO_INFO = "No encuentro esta informacion en los documentos disponibles."

    leaked = detect_generic_knowledge_leak(final_response) or detect_model_refusal(final_response)

    # Se busca cualquier variante de "no lo se" en toda la respuesta, no solo
    # la frase fija exacta al principio: el modelo a veces la antepone con
    # texto propio (ej. "La respuesta es: No encuentro...") o la parafrasea
    # ("No tengo esta informacion"), lo que antes hacia que no se vaciaran
    # las fuentes aunque el propio modelo diga que no sabe la respuesta.
    # Deteccion unificada con /api/patient-chat via detect_no_info_statement
    # (agosto 2026): antes /api/chat solo comprobaba un prefijo literal mas
    # estrecho que el usado en pacientes.
    if detect_no_info_statement(final_response):
        final_response = CANNED_NO_INFO
        sources_used = []
    elif leaked:
        final_response = CANNED_NO_INFO
        sources_used = []

    result = {
        "response": final_response,
        "sources": sources_used,
    }
    # Indicador de cobertura documental, siempre incluido (no solo en modo
    # debug): clasifica que tan cerca estuvo el mejor fragmento recuperado
    # de la pregunta, usando la misma distancia que ya se calcula para el
    # filtro de relevancia. Umbrales elegidos de forma conservadora sobre
    # el rango observado en la sesion de auditoria de agosto 2026 (la
    # mayoria de respuestas bien fundamentadas caian por debajo de 480).
    # No sustituye una verificacion clinica humana, es solo una senal
    # orientativa para el profesional.
    if distances and sources_used:
        best_distance = distances[0]
        if best_distance <= 400:
            result["coverage"] = "alta"
        elif best_distance <= 600:
            result["coverage"] = "media"
        else:
            result["coverage"] = "baja"
    else:
        result["coverage"] = None

    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": request.top_k,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fragments_retrieved": len(fragments),
        }

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)

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


# Categorias que NO corresponden a un PDF real (son citas bibliograficas
# breves generadas por los indexadores de la Knowledge Base JSON y de la
# biblioteca ampliada de Excel), asi que nunca tiene sentido intentar servir
# un archivo para ellas.
NON_PDF_CATEGORIES = {"05_ClinicalKB_JSON", "07_Biblioteca_Ampliada_253"}


@app.get("/api/document/{category}/{filename}")
def get_document(category: str, filename: str, page: int = 1, highlight: str = ""):
    """Sirve el PDF original de una fuente citada, para abrirlo en la pagina
    exacta (fragmento #page=N, interpretado por el visor de PDF nativo del
    navegador) y, si se recibe `highlight`, con el fragmento de texto
    recuperado por el RAG resaltado en amarillo dentro de la propia pagina.

    El resaltado busca linea por linea (no el bloque completo de una vez,
    que suele fallar por saltos de linea internos del PDF) y marca todas las
    coincidencias encontradas. Si no encuentra ninguna coincidencia (texto
    reformateado, guiones de particion de palabra, etc.), sirve el PDF igual,
    sin resaltado, en vez de fallar.

    Proteccion contra path traversal: se prueban rutas candidatas dentro de
    DOCUMENTS_DIR y se verifica, con el path ya resuelto (realpath), que el
    resultado sigue estando dentro de DOCUMENTS_DIR antes de servir nada.
    Category/filename con ".." o rutas absolutas nunca superan esta
    comprobacion.
    """
    if category in NON_PDF_CATEGORIES:
        raise HTTPException(status_code=404, detail="Esta fuente es una cita bibliografica breve, no tiene un PDF asociado para abrir.")

    documents_real = os.path.realpath(DOCUMENTS_DIR)
    candidate_paths = [
        os.path.join(DOCUMENTS_DIR, "TB_full", category, filename),
        os.path.join(DOCUMENTS_DIR, category, filename),
    ]

    resolved_path = None
    for candidate in candidate_paths:
        candidate_real = os.path.realpath(candidate)
        is_inside_documents = candidate_real == documents_real or candidate_real.startswith(documents_real + os.sep)
        if is_inside_documents and os.path.isfile(candidate_real):
            resolved_path = candidate_real
            break

    if resolved_path is None:
        raise HTTPException(status_code=404, detail="No se encontro el PDF de esta fuente en el servidor.")

    if not highlight:
        response = FileResponse(resolved_path, media_type="application/pdf")
        response.headers["Content-Disposition"] = "inline"
        return response

    # Limite defensivo: un fragmento recuperado nunca deberia superar
    # CHUNK_SIZE (2000 caracteres), pero se recorta por si acaso para evitar
    # busquedas excesivamente largas sobre el PDF.
    highlight = highlight[:2500]

    try:
        pdf = fitz.open(resolved_path)
        if 1 <= page <= len(pdf):
            pdf_page = pdf[page - 1]
            lines = [line.strip() for line in highlight.split("\n") if len(line.strip()) > 3]
            for line in lines:
                quads = pdf_page.search_for(line, quads=True)
                for quad in quads:
                    pdf_page.add_highlight_annot(quad)
        pdf_bytes = pdf.tobytes()
        pdf.close()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )
    except Exception:
        # Si algo falla al resaltar (PDF corrupto, texto no encontrado, etc.),
        # se sirve el PDF original sin resaltado en vez de romper la
        # experiencia del usuario con un error.
        response = FileResponse(resolved_path, media_type="application/pdf")
        response.headers["Content-Disposition"] = "inline"
        return response


@app.post("/api/patient-chat")
def patient_chat(request: PatientChatRequest):
    lang_name = resolve_lang_name(request.lang)
    canned_no_info = resolve_canned_no_info(request.lang)

    retrieval_query = build_retrieval_query(request.message, request.history)
    fragments, metadatas, distances = retrieve(retrieval_query, 8)

    # La lista TB_KEYWORDS solo cubre espanol: en arabe/urdu nunca habria
    # coincidencia, lo que forzaria siempre el umbral estricto (480) aunque
    # la pregunta sea legitima. Como esta app esta dedicada integramente a
    # tuberculosis, tratamos estos dos idiomas como "dentro de dominio" por
    # defecto y usamos el umbral permisivo (750).
    has_keyword = is_tb_related(request.message) or request.lang in ("ar", "ur")

    if not is_relevant(fragments, distances, has_keyword):
        log_usage_pattern("/api/patient-chat", "sin_cobertura", lang=request.lang)
        return {"response": canned_no_info}

    context_parts = [frag for frag in fragments]
    context_text = "\n\n---\n\n".join(context_parts)
    history_block = build_history_block(request.history)

    user_prompt = f"{history_block}IDIOMA DE RESPUESTA: {lang_name}\n\nCONTEXTO:\n{context_text}\n\nPREGUNTA DEL PACIENTE:\n{request.message}"

    final_response = generate_response(PATIENT_SYSTEM_PROMPT, user_prompt)

    CANNED_NO_INFO_PATIENT = "No encuentro esta informacion en los documentos disponibles."

    # Deteccion unificada con /api/chat via detect_no_info_statement
    # (agosto 2026): misma lista de variantes de "no lo se" en ambos
    # endpoints, para que un patron nuevo anadido en el futuro proteja a
    # los dos a la vez en vez de mantenerse como dos listas separadas.
    said_no_info = detect_no_info_statement(final_response)

    leaked = detect_generic_knowledge_leak(final_response) or detect_model_refusal(final_response)

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

    # Cobertura interna, solo para el registro de patrones de uso (no se
    # muestra al paciente, igual que las fuentes: aqui usamos los mismos
    # umbrales que en /api/chat para mantener las estadisticas comparables
    # entre ambos endpoints).
    if distances:
        best_distance = distances[0]
        if best_distance <= 400:
            internal_coverage = "alta"
        elif best_distance <= 600:
            internal_coverage = "media"
        else:
            internal_coverage = "baja"
    else:
        internal_coverage = None
    log_usage_pattern("/api/patient-chat", internal_coverage, lang=request.lang)

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
