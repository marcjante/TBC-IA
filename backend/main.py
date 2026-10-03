"""
TBC-AI - backend/main.py

Backend FastAPI: configuracion de la app, modelos Pydantic y orquestacion de
cada endpoint. La logica vive en los modulos:
- safety.py (filtros de fuga / "no lo se" / relevancia)
- clinical_rules.py (signos de alarma, interacciones, cifras, citas)
- triage.py (clasificador de intencion, expansion de consulta)
- verification.py (verificacion de afirmaciones, comparacion de modelos)
- translation.py (traduccion local para pacientes)
- prompts.py, languages.py, rag.py, llm.py

Revision de seguridad clinica y de API (octubre 2026): ver
documentacion/revisiones/. Los cambios de comportamiento se indican junto a
cada punto con su codigo del informe (C1, A1, M3...).
"""

import logging
import os
import json
import re
import secrets
import time
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
import ollama
import fitz

from backend.config import (
    CHAT_MODEL, DOCUMENTS_DIR, GUIDES_DIR, PATIENT_DIR, PROJECT_ROOT, collection,
    ADMIN_TOKEN, ALLOWED_ORIGINS, ALLOWED_HOSTS, DEV_MODE,
)
from backend.safety import is_tb_related, detect_generic_knowledge_leak, detect_model_refusal, detect_no_info_statement
from backend.prompts import SYSTEM_PROMPT, PATIENT_SYSTEM_PROMPT
from backend.languages import (
    resolve_canned_urgencia, resolve_canned_riesgo_autolesion, resolve_nota_riesgo,
    resolve_no_info_with_referral, resolve_bloqueo_cifras, resolve_alerta_toxicidad,
    resolve_traduccion_no_verificada,
)
from backend.rag import (
    is_relevant, index_single_pdf, query_sota_fallback, query_sota_alerts, query_llamafile_response,
    query_master_bibliography, search_pubmed_live, get_drug_safety_info, hybrid_retrieve,
)
from backend.llm import generate_response
from backend.clinical_rules import (
    check_red_flags, interaction_warnings, population_caveat, has_clinical_figures, find_invalid_citations,
    figures_supported_by_context,
)
from backend.triage import (
    classify_intent, expand_query,
    PRO_ALERTA_SIGNO_ALARMA, PRO_ALERTA_AUTOLESION,
)
from backend.verification import verify_claims_with_llm, compare_with_llamafile
from backend.translation import translate_to_spanish, translate_from_spanish, translate_abstract

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tbc.main")

app = FastAPI(title="TBC-AI Backend")

# Solo la propia interfaz (8001) y el panel (8090) pueden llamar a la API
# desde el navegador; antes cualquier web abierta podia hacerlo (CORS "*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)
# Rechaza peticiones cuyo Host no sea 127.0.0.1/localhost (DNS rebinding).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


# ------------------------------------------------------------------------------
# Modelos (limites de entrada: M5 y seguridad de API)
# ------------------------------------------------------------------------------
MAX_MESSAGE_CHARS = 2000


class HistoryTurn(BaseModel):
    # Solo roles conocidos: antes el cliente podia enviar cualquier "role" y
    # colar "respuestas previas" inventadas.
    role: Literal["user", "bot", "assistant"]
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    top_k: int = Field(8, ge=1, le=10)
    debug: bool = False
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)


class PatientChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    lang: Literal["es", "ca", "ar", "ur"] = "es"
    debug: bool = False
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)


@app.get("/api/health")
def health():
    try:
        ollama.list()
        doc_count = collection.count()
        return {"status": "ok", "model": CHAT_MODEL, "documentos_indexados": doc_count}
    except Exception as e:
        # No se devuelve el texto de la excepcion al cliente (B2).
        logger.warning("health: %s", type(e).__name__)
        return {"status": "error"}


# ------------------------------------------------------------------------------
# Utilidades compartidas
# ------------------------------------------------------------------------------
MAX_HISTORY_TURNS = 2  # ultimo intercambio (1 pregunta + 1 respuesta)
MAX_HISTORY_CHARS = 400
MAX_SOURCES_FOR_GENERATION = 7
CANNED_NO_INFO = "No encuentro esta informacion en los documentos disponibles."
CLINICAL_CATEGORIES = {"01_WHO", "02_CDC", "05_ClinicalKB_JSON"}

PRO_NOTA_NO_VERIFICADO = (
    "Nota: parte de esta información no se ha podido verificar directamente contra las "
    "fuentes documentales. Coméntalo con tu equipo médico antes de actuar según esto."
)
PRO_BLOQUEO_CIFRAS = (
    "⚠️ La respuesta generada incluía cifras (dosis, duraciones o pautas) que no se han podido "
    "verificar en las fuentes recuperadas, así que no se muestra. Consulta directamente las "
    "fuentes listadas debajo."
)
PRO_NOTA_TRIAJE = (
    "Nota: no se ha podido completar la comprobación automática de signos de alarma; "
    "valora la urgencia clínicamente."
)
PATIENT_NOTA_DERIVACION = (
    "Si tienes síntomas nuevos o te encuentras peor, contacta con tu equipo de tuberculosis; "
    "ante síntomas graves, llama al 112."
)


def build_retrieval_query(message, history):
    """Si el mensaje es muy corto (probable seguimiento, ej. '¿y en niños?'),
    se combina con la ultima pregunta del usuario para la busqueda."""
    if len(message.strip()) >= 40 or not history:
        return message
    previous_user_msgs = [h.content for h in history if h.role == "user"]
    if not previous_user_msgs:
        return message
    return previous_user_msgs[-1] + " " + message


def build_history_block(history, user_turns_only=False):
    """Ultimo intercambio recortado, para dar continuidad. En el chat de
    pacientes solo se incluyen los turnos del propio usuario (M5): las
    "respuestas previas" las manda el cliente y no son de fiar."""
    if not history:
        return ""
    turns = [t for t in history if t.role == "user"] if user_turns_only else list(history)
    recent = turns[-MAX_HISTORY_TURNS:]
    if not recent:
        return ""
    lines = [("Usuario" if t.role == "user" else "Asistente") + ": " + t.content[:MAX_HISTORY_CHARS] for t in recent]
    return ("HISTORIAL RECIENTE (para dar continuidad a la conversacion, no es una fuente de "
            "informacion clinica):\n" + "\n".join(lines) + "\n\n")


USAGE_LOG_PATH = os.path.join(PROJECT_ROOT, "usage_patterns.jsonl")


def log_usage_pattern(endpoint, coverage, lang=None):
    """Registro ligero de patrones de uso (cobertura e idioma).

    Revision de seguridad clinica (octubre 2026, C2): NUNCA se guarda el texto
    de la pregunta, en ningun endpoint. Antes /api/chat lo guardaba completo,
    incluidos los casos de autolesion y urgencias: datos de salud de
    categoria especial (art. 9 RGPD) sin anonimizar ni plazo de borrado.
    Un fallo de escritura no rompe la respuesta, pero queda registrado."""
    entry = {"timestamp": datetime.now().isoformat(timespec="seconds"), "endpoint": endpoint, "coverage": coverage}
    if lang is not None:
        entry["lang"] = lang
    try:
        with open(USAGE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning("log_usage_pattern: no se pudo escribir (%s)", type(e).__name__)


def coverage_level(distances, fallback_used, has_sources):
    """Indicador orientativo de cobertura documental. Usa la MEJOR distancia
    (min), igual que is_relevant (B4: antes se usaba distances[0])."""
    if fallback_used and has_sources:
        return "complementaria"
    if distances and has_sources:
        best = min(distances)
        return "alta" if best <= 400 else "media" if best <= 600 else "baja"
    return None


def safe_generate(system_prompt, user_prompt):
    """Genera la respuesta; devuelve None si el LLM falla o tarda demasiado
    (M8: antes acababa en error 500 sin mensaje de derivacion)."""
    _t0 = time.time()
    try:
        text = generate_response(system_prompt, user_prompt)
    except Exception as e:
        logger.warning("generate_response: fallo (%s)", type(e).__name__)
        return None
    logger.info("generate_response: %.1fs", time.time() - _t0)
    return text


def claims_with_figures(claims, context_parts):
    """Afirmaciones no respaldadas que contienen dosis/duraciones/pautas (A1)
    y cuyas cifras NO aparecen en el contexto. Si la cifra si esta en las
    fuentes (p. ej. "3 meses" frente a "three months"), no se bloquea: el
    verificador LLM confunde a menudo traducciones con invenciones."""
    context_text = "\n".join(context_parts)
    return [c for c in (claims or []) if has_clinical_figures(c) and not figures_supported_by_context(c, context_text)]


def retrieve_context(question, history, top_k):
    """Recuperacion comun a ambos chats. Devuelve (fragments, metadatas,
    distances, fallback_used, sota_alerts) o fragments=None si no hay
    cobertura."""
    retrieval_query = expand_query(build_retrieval_query(question, history))
    _t0 = time.time()
    fragments, metadatas, distances = hybrid_retrieve(retrieval_query, top_k)
    logger.info("hybrid_retrieve: %.1fs", time.time() - _t0)
    if is_relevant(fragments, distances, is_tb_related(question)):
        return fragments, metadatas, distances, False, []
    fb_fragments, fb_metadatas, fb_info = query_sota_fallback(retrieval_query)
    alerts = fb_info.get("alert") if isinstance(fb_info, dict) and isinstance(fb_info.get("alert"), list) else []
    if alerts:
        return None, None, None, False, alerts
    if fb_fragments:
        return fb_fragments, fb_metadatas, [], True, []
    return None, None, None, False, []


# ------------------------------------------------------------------------------
# Chat profesional
# ------------------------------------------------------------------------------
@app.post("/api/chat")
def chat(request: ChatRequest):
    question = request.message
    prefix = ""          # avisos que se anteponen a la respuesta
    notes = []           # avisos que se añaden al final
    risk = False         # mostrar la nota de "no verificado"

    # Triaje (B1): en el chat profesional un signo de alarma no corta la
    # respuesta; se antepone un aviso de urgencia y se responde con las guias.
    red_flag = check_red_flags(question)
    intencion, triage_ok = classify_intent(question)
    if red_flag or intencion == "urgencia_medica":
        prefix += PRO_ALERTA_SIGNO_ALARMA
    if intencion == "riesgo_autolesion":
        prefix += PRO_ALERTA_AUTOLESION
    if not triage_ok:
        notes.append(PRO_NOTA_TRIAJE)

    # Alertas del motor complementario: siempre, antes de generar (A3).
    sota_alerts = query_sota_alerts(question)
    if sota_alerts:
        prefix += "⚠️ " + " ".join(sota_alerts) + "\n\n"
    elif sota_alerts is None:
        risk = True

    fragments, metadatas, distances, fallback_used, fb_alerts = retrieve_context(question, request.history, request.top_k)
    if fb_alerts:
        prefix += "⚠️ " + " ".join(fb_alerts) + "\n\n"
    if fragments is None:
        log_usage_pattern("/api/chat", "alerta_clinica" if fb_alerts else "sin_cobertura")
        return {"response": (prefix + CANNED_NO_INFO).strip(), "sources": [], "coverage": None}

    context_parts, sources_used = [], []
    for frag, meta in zip(fragments, metadatas):
        page_part = ", pagina: " + str(meta["page"]) if meta.get("page") is not None else ""
        context_parts.append("[Fuente: " + meta["source"] + ", categoria: " + meta["category"] + page_part + "]\n" + frag)
        sources_used.append({"source": meta["source"], "category": meta["category"], "page": meta.get("page"), "text": frag})

    # Bibliografia cientifica verificada (complementaria). Se etiqueta como
    # evidencia de investigacion, no como recomendacion clinica (M6).
    for bib in query_master_bibliography(question, limit=2):
        if bib.get("retraction_status") != "ninguna":
            continue
        cite = f"{bib.get('journal') or 'revista desconocida'} ({bib.get('year') or 's.f.'})"
        context_parts.append(
            f"[Fuente: bibliografia cientifica verificada, {cite} — EVIDENCIA DE INVESTIGACION, "
            f"NO ES UNA RECOMENDACION CLINICA]\n{bib.get('title', '')}\n{bib.get('abstract', '')}"
        )
        sources_used.append({
            "source": f"PubMed/Europe PMC - {cite}", "category": "bibliografia_cientifica", "page": None,
            "text": bib.get("abstract") or bib.get("title", ""), "doi": bib.get("doi"), "pmid": bib.get("pmid"),
        })

    # Las MISMAS fuentes para generar, citar y verificar (A7).
    context_parts = context_parts[:MAX_SOURCES_FOR_GENERATION]
    sources_used = sources_used[:MAX_SOURCES_FOR_GENERATION]
    context_text = "\n\n---\n\n".join(context_parts)
    user_prompt = build_history_block(request.history) + "CONTEXTO:\n" + context_text + "\n\nPREGUNTA DEL USUARIO:\n" + question

    final_response = safe_generate(SYSTEM_PROMPT, user_prompt)
    canned = final_response is None or detect_no_info_statement(final_response) \
        or detect_generic_knowledge_leak(final_response) or detect_model_refusal(final_response)
    if canned:
        final_response, sources_used = CANNED_NO_INFO, []

    coverage = coverage_level(distances, fallback_used, bool(sources_used))
    result = {"sources": sources_used, "coverage": coverage}
    debug_info = {}

    unsupported = None
    if not canned:  # no se verifica el propio mensaje de "sin informacion" (M7)
        _t0 = time.time()
        unsupported = verify_claims_with_llm(context_parts, final_response)
        logger.info("verify_claims_with_llm: %.1fs", time.time() - _t0)
        invalid_citations = find_invalid_citations(final_response, sources_used)
        debug_info.update({"llm_unsupported_claims": unsupported, "invalid_citations": invalid_citations})

        if claims_with_figures(unsupported, context_parts):
            # A1: cifras no respaldadas -> no se muestra la respuesta.
            final_response = PRO_BLOQUEO_CIFRAS
        else:
            # Verificador caido = riesgo (fallar cerrado), igual que
            # afirmaciones sin respaldo, citas falsas o cobertura baja.
            risk = risk or unsupported is None or bool(unsupported) or bool(invalid_citations) \
                or coverage in ("baja", "complementaria")
            caveat = population_caveat(question, final_response)
            if caveat:
                notes.append(caveat)
        notes.extend(interaction_warnings(question, final_response))

    if risk and not canned:
        notes.append(PRO_NOTA_NO_VERIFICADO)
    result["response"] = (prefix + final_response + ("\n\n" + "\n\n".join(notes) if notes else "")).strip()

    # Segundo modelo (Mistral): solo en modo debug. Antes se ejecutaba en
    # cada respuesta con riesgo aunque su resultado solo se usaba en debug.
    if request.debug:
        debug_info.update({"model": CHAT_MODEL, "top_k": request.top_k, "fallback_used": fallback_used,
                           "top1_distance": min(distances) if distances else None})
        if risk and sources_used:
            response_b = query_llamafile_response(context_text, question)
            if response_b is not None:
                comparison = compare_with_llamafile(final_response, response_b)
                if comparison is not None:
                    debug_info["dual_model_comparison"] = {"response_b": response_b, **comparison}
        result["debug_info"] = debug_info

    log_usage_pattern("/api/chat", coverage)
    return result


# ------------------------------------------------------------------------------
# Subida de documentos (C1)
# ------------------------------------------------------------------------------
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9 _\-.()áéíóúÁÉÍÓÚñÑçÇàèòÀÈÒüÜ]{1,150}\.pdf$", re.IGNORECASE)


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form("sin_categoria"),
    x_admin_token: str = Header(default=""),
):
    """Sube e indexa un PDF. Revision de seguridad (octubre 2026, C1): antes
    no pedia autenticacion y aceptaba rutas (path traversal), asi que
    cualquier web abierta en el navegador podia escribir PDFs en el disco o
    colar una "guia" con dosis falsas que el chat citaria como fuente."""
    if not ADMIN_TOKEN:
        raise HTTPException(403, "La subida de documentos esta desactivada (falta TBC_ADMIN_TOKEN).")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "Token de administrador incorrecto.")
    if not _SAFE_NAME_RE.match(category):
        raise HTTPException(400, "Categoria no valida (solo letras, numeros, _ y -).")
    filename = os.path.basename(file.filename or "")
    if not _SAFE_FILENAME_RE.match(filename):
        raise HTTPException(400, "Nombre de archivo no valido: debe ser un .pdf sin rutas ni caracteres especiales.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "El PDF supera el limite de 25 MB.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(400, "El archivo no es un PDF valido.")

    documents_real = os.path.realpath(DOCUMENTS_DIR)
    category_dir = os.path.realpath(os.path.join(DOCUMENTS_DIR, category))
    dest_path = os.path.realpath(os.path.join(category_dir, filename))
    if not dest_path.startswith(documents_real + os.sep):
        raise HTTPException(400, "Ruta de destino no valida.")
    os.makedirs(category_dir, exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(content)

    try:
        chunks_created = index_single_pdf(dest_path, category, filename)
    except Exception as e:
        logger.warning("upload: fallo al indexar (%s)", type(e).__name__)
        return {"status": "error", "detail": "Archivo guardado pero fallo la indexacion."}

    logger.info("upload: %s/%s indexado (%s fragmentos)", category, filename, chunks_created)
    return {"status": "ok", "filename": filename, "category": category,
            "chunks_indexed": chunks_created, "total_documentos_indexados": collection.count()}


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


# ------------------------------------------------------------------------------
# Chat de pacientes
# ------------------------------------------------------------------------------
def _localize(spanish_text, lang):
    """Traduce la respuesta final (compuesta en castellano) al idioma del
    paciente. Si la traduccion falla o altera alguna cifra (A6), se muestra
    en castellano precedida de un aviso en su idioma."""
    if lang == "es":
        return spanish_text
    translated = translate_from_spanish(spanish_text, lang)
    if translated is None:
        return resolve_traduccion_no_verificada(lang) + "\n\n" + spanish_text
    return translated


@app.post("/api/patient-chat")
def patient_chat(request: PatientChatRequest):
    lang = request.lang
    endpoint = "/api/patient-chat"

    # C4: todo el pipeline de seguridad trabaja en castellano. Las preguntas
    # en catalan, arabe o urdu se traducen antes de clasificarlas.
    question = translate_to_spanish(request.message, lang)
    translation_failed = question is None
    if translation_failed:
        question = request.message

    # 1) Signos de alarma deterministas (sobre el original y la traduccion).
    red_flag = check_red_flags(request.message, question)
    if red_flag:
        log_usage_pattern(endpoint, f"red_flag_{red_flag}", lang=lang)
        return {"response": resolve_canned_urgencia(lang)}

    # 2) Clasificador de intencion por LLM.
    intencion, triage_ok = classify_intent(question)
    if intencion == "urgencia_medica":
        log_usage_pattern(endpoint, "urgencia_medica_general", lang=lang)
        return {"response": resolve_canned_urgencia(lang)}
    if intencion == "riesgo_autolesion":
        log_usage_pattern(endpoint, "riesgo_autolesion", lang=lang)
        return {"response": resolve_canned_riesgo_autolesion(lang)}

    # 3) Alertas del motor complementario: siempre, antes de generar (A3).
    sota_alerts = query_sota_alerts(question)
    if sota_alerts:
        log_usage_pattern(endpoint, "alerta_clinica", lang=lang)
        return {"response": resolve_alerta_toxicidad(lang)}

    # En otros idiomas no se combina con el historial para la busqueda (el
    # historial esta en el idioma del paciente y la busqueda en castellano).
    retrieval_history = request.history if lang == "es" else []
    fragments, metadatas, distances, fallback_used, fb_alerts = retrieve_context(question, retrieval_history, 8)
    if fb_alerts:
        log_usage_pattern(endpoint, "alerta_clinica", lang=lang)
        return {"response": resolve_alerta_toxicidad(lang)}
    if fragments is None:
        log_usage_pattern(endpoint, "sin_cobertura", lang=lang)
        return {"response": resolve_no_info_with_referral(lang)}

    # Fuentes clinicas (OMS, CDC, KB) primero; vigilancia epidemiologica despues.
    paired = sorted(zip(fragments, metadatas), key=lambda p: 0 if p[1].get("category") in CLINICAL_CATEGORIES else 1)
    context_parts = [frag for frag, _ in paired[:MAX_SOURCES_FOR_GENERATION]]
    context_text = "\n\n---\n\n".join(context_parts)
    user_prompt = (build_history_block(request.history, user_turns_only=True)
                   + "IDIOMA DE RESPUESTA: castellano\n\nCONTEXTO:\n" + context_text
                   + "\n\nPREGUNTA DEL PACIENTE:\n" + question)

    final_response = safe_generate(PATIENT_SYSTEM_PROMPT, user_prompt)
    if final_response is None or detect_no_info_statement(final_response) \
            or detect_generic_knowledge_leak(final_response) or detect_model_refusal(final_response):
        log_usage_pattern(endpoint, "sin_cobertura", lang=lang)
        # M1: siempre en el idioma del paciente (antes salia en castellano).
        return {"response": resolve_no_info_with_referral(lang)}

    # Sin nombres de archivo, URLs ni citas para el paciente (regla 6 del prompt).
    final_response = re.sub(r"\(Fuente:.*?\)", "", final_response, flags=re.IGNORECASE | re.DOTALL)
    final_response = re.sub(r"https?://\S+", "", final_response)
    final_response = re.sub(r"\S+\.pdf", "", final_response, flags=re.IGNORECASE)
    final_response = re.sub(r"[ \t]{2,}", " ", final_response).strip()

    coverage = coverage_level(distances, fallback_used, True)
    unsupported = verify_claims_with_llm(context_parts, final_response)
    if claims_with_figures(unsupported, context_parts):
        # A1: una dosis o duracion no respaldada no llega al paciente.
        log_usage_pattern(endpoint, "bloqueo_cifras", lang=lang)
        return {"response": resolve_bloqueo_cifras(lang)}

    notes = []
    caveat = population_caveat(question, final_response)
    if caveat:
        notes.append(caveat)
    notes.extend(interaction_warnings(question, final_response))
    risk = unsupported is None or bool(unsupported) or coverage in ("baja", "complementaria") or sota_alerts is None
    if risk:
        notes.append(resolve_nota_riesgo("es"))
    if not triage_ok or translation_failed:
        notes.append(PATIENT_NOTA_DERIVACION)

    spanish_answer = final_response + ("\n\n" + "\n\n".join(notes) if notes else "")
    result = {"response": _localize(spanish_answer, lang)}

    # debug_info solo en modo desarrollo: antes se devolvia siempre la
    # respuesta en bruto de Mistral, sin ningun filtro (A2).
    if request.debug and DEV_MODE:
        result["debug_info"] = {"model": CHAT_MODEL, "fallback_used": fallback_used, "coverage": coverage,
                                "llm_unsupported_claims": unsupported, "question_es": question}

    log_usage_pattern(endpoint, coverage, lang=lang)
    return result


@app.get("/panel", response_class=HTMLResponse)
def panel():
    """Muestra incrustado el Panel TBC-IA (puerto 8090) con el estado de
    los siete servicios, para verlo sin salir de TBC-AI. Si el panel no
    esta corriendo, se ve un mensaje de error dentro del propio iframe
    (no rompe esta pagina)."""
    return """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Panel TBC-IA (incrustado)</title>
<style>
  body { margin: 0; padding: 0; background: #0f1117; }
  .topbar {
    background: #1a1d27; color: #9098a8; padding: 10px 20px;
    font-family: -apple-system, sans-serif; font-size: 13px;
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1px solid #2a2e3a;
  }
  .topbar a { color: #4ade80; text-decoration: none; }
  iframe { width: 100%; height: calc(100vh - 41px); border: none; }
</style>
</head>
<body>
  <div class="topbar">
    <span>Panel TBC-IA — vista incrustada (puerto 8090)</span>
    <a href="http://127.0.0.1:8090" target="_blank">Abrir en pestaña aparte ↗</a>
  </div>
  <iframe src="http://127.0.0.1:8090"></iframe>
</body>
</html>
"""


HOME_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "home.html")


@app.get("/", response_class=HTMLResponse)
def home():
    with open(HOME_TEMPLATE_PATH, encoding="utf-8") as f:
        html = f.read()
    return html.replace("{CHAT_MODEL_PLACEHOLDER}", CHAT_MODEL)


@app.get("/api/panel-status")
def panel_status():
    """Comprueba desde el propio servidor (no desde el navegador, para
    evitar problemas de CORS) si el Panel TBC-IA (puerto 8090) esta
    conectado. Fail-open: devuelve connected=False si no responde."""
    import requests
    try:
        resp = requests.get("http://127.0.0.1:8090", timeout=1.5)
        return {"connected": resp.status_code == 200}
    except requests.RequestException:
        return {"connected": False}


@app.get("/api/bibliography-search")
def bibliography_search(query: str = Query(..., min_length=1, max_length=300), limit: int = Query(5, ge=1, le=20)):
    """Busca en la bibliografia verificada (tbc_master.db, puerto 8002).
    Fail-open: lista vacia si falla."""
    try:
        results = query_master_bibliography(query, limit=limit)
    except Exception:
        results = []
    results = [r for r in results if r.get("retraction_status") == "ninguna"]
    return {"query": query, "results": results}


@app.get("/api/bibliography-search-live")
def bibliography_search_live(query: str = Query(..., min_length=1, max_length=300), limit: int = Query(5, ge=1, le=20)):
    """Busca en vivo en PubMed (internet), sin verificacion. La interfaz
    avisa de que no se escriban datos de pacientes (B5)."""
    try:
        results = search_pubmed_live(query, max_results=limit)
    except Exception:
        results = []
    return {"query": query, "results": results}


@app.post("/api/translate")
def translate_text(payload: TranslateRequest):
    """Traduce al castellano un resumen de articulo con el modelo local.
    POST con cuerpo JSON: el texto ya no viaja en la URL (no acaba en logs)."""
    try:
        return {"translated": translate_abstract(payload.text), "error": False}
    except Exception as e:
        logger.warning("translate: fallo (%s)", type(e).__name__)
        return {"translated": None, "error": True}


@app.get("/api/aemps-search")
def aemps_search(query: str = Query(..., min_length=1, max_length=120)):
    """Ficha tecnica oficial de CIMA (AEMPS). Fail-open: result=None."""
    try:
        result = get_drug_safety_info(query)
    except Exception:
        result = None
    return {"query": query, "result": result}


app.mount("/guides", StaticFiles(directory=GUIDES_DIR, html=True), name="guides")
app.mount("/patient", StaticFiles(directory=PATIENT_DIR, html=True), name="patient")
