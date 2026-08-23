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
from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response, query_master_bibliography, search_pubmed_live, get_drug_safety_info
from backend.llm import generate_response


app = FastAPI(title="TBC-AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# VERIFICACION DE AFIRMACIONES VIA LLM (segunda pasada) - agosto 2026
# ==============================================================================
# Alternativa/complemento al chequeo NLI de verify_groundedness() en rag.py:
# el modelo NLI generico no distingue bien sustituciones finas de un termino
# concreto por otro con la misma plantilla de frase (ej. "ansiedad" -> "soledad"
# manteniendo "es un sintoma comun de tuberculosis"). Se le pide al propio LLM
# que revise sus afirmaciones contra el contexto, en una llamada aparte.
# Solo informativo (debug_info), no altera la respuesta real al paciente.

VERIFICATION_SYSTEM_PROMPT = """Eres un revisor clinico. Se te da un CONTEXTO (fragmentos de fuentes documentales) y una RESPUESTA que otro asistente genero a partir de ese contexto para un paciente o profesional.

Tu tarea: identifica frases de la RESPUESTA que afirman algo clinico o factual concreto que NO esta respaldado, ni literalmente ni por una inferencia razonable, en el CONTEXTO. El asistente que genero la respuesta a veces "rellena" con afirmaciones inventadas que sustituyen un termino del contexto por otro parecido (por ejemplo, el contexto habla de ansiedad y la respuesta afirma algo especifico sobre soledad, sin que el contexto lo respalde).

NO marques:
- Frases genericas de acompanamiento ("habla con tu equipo medico", "no estas solo en esto").
- Reformulaciones fieles del contexto, aunque cambien las palabras.
- Recomendaciones de sentido comun no especificas (respirar hondo, hablar con alguien de confianza).

SI marca:
- Afirmaciones especificas sobre sintomas, causas, pronosticos, o tratamientos que no aparecen en el contexto.

Responde EXCLUSIVAMENTE con un JSON con este formato exacto, sin texto antes ni despues:
{"unsupported_claims": ["frase exacta 1", "frase exacta 2"]}

Si todas las frases estan respaldadas, responde exactamente:
{"unsupported_claims": []}
"""


def parse_verification_response(raw):
    """Extrae la lista unsupported_claims del texto devuelto por el LLM,
    tolerando que venga envuelto en bloques de codigo o con texto alrededor
    (Llama a veces no sigue la instruccion de "solo JSON" al pie de la letra).
    Devuelve None si no se puede interpretar nada (fail-open)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        claims = parsed.get("unsupported_claims", [])
        return claims if isinstance(claims, list) else None
    except (json.JSONDecodeError, AttributeError):
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            claims = parsed.get("unsupported_claims", [])
            return claims if isinstance(claims, list) else None
        except (json.JSONDecodeError, AttributeError):
            return None
    return None


def normalize_text_for_claim_check(text):
    text = text.lower()
    for a, b in [("\u00e1", "a"), ("\u00e9", "e"), ("\u00ed", "i"), ("\u00f3", "o"), ("\u00fa", "u"), ("\u00f1", "n")]:
        text = text.replace(a, b)
    text = re.sub(r"[^\w\s]", " ", text)
    return text


def claim_actually_in_response(claim, response_text, threshold=0.5):
    """Comprueba que una afirmacion marcada por el verificador realmente
    aparece (por solapamiento de palabras) en el texto de la respuesta
    revisada. Descubierto en pruebas (agosto 2026): el propio LLM
    verificador puede marcar una frase que ni siquiera esta en el texto
    original — una alucinacion del verificador, no una deteccion real."""
    claim_words = set(normalize_text_for_claim_check(claim).split())
    if not claim_words:
        return False
    response_words = set(normalize_text_for_claim_check(response_text).split())
    overlap = len(claim_words & response_words) / len(claim_words)
    return overlap >= threshold


def verify_claims_with_llm(sources_texts, response_text):
    """Pide al propio LLM (via generate_response, ya usado en el resto de
    TBC-AI) que revise la respuesta ya generada contra las fuentes, en una
    llamada aparte. NO decide nada sobre la respuesta: solo informa.
    Devuelve None si falla cualquier paso (fail-open, no bloquea el flujo
    normal por un fallo de esta verificacion adicional).

    Filtra ademas las afirmaciones marcadas que no aparecen realmente en
    response_text (alucinaciones del propio verificador, ver
    claim_actually_in_response)."""
    if not sources_texts:
        return None

    # Limitar el tamaño del contexto que ve el VERIFICADOR (no afecta al
    # contexto usado para generar la respuesta real, solo a esta segunda
    # llamada de revision). Con contextos muy largos (muchas fuentes) el
    # verificador puede "distraerse" y responder una pregunta que aparece
    # dentro de las fuentes en vez de hacer la comparacion pedida —
    # detectado en pruebas reales el 22 de agosto de 2026 con 10 fuentes.
    MAX_VERIFIER_CONTEXT_CHARS = 6000
    context_text = "\n\n---\n\n".join(sources_texts)
    context_for_verifier = context_text
    truncated = False
    if len(context_for_verifier) > MAX_VERIFIER_CONTEXT_CHARS:
        context_for_verifier = context_for_verifier[:MAX_VERIFIER_CONTEXT_CHARS] + "\n\n[...contexto recortado para la verificacion...]"
        truncated = True

    # La instruccion se repite al FINAL, despues del contexto, para
    # anclar mejor la tarea cuando el contexto es largo (evita que el
    # modelo responda a algo que aparece dentro del propio contexto).
    user_msg = (
        f"CONTEXTO:\n{context_for_verifier}\n\nRESPUESTA A REVISAR:\n{response_text}\n\n"
        "Recuerda: tu unica tarea es responder EXCLUSIVAMENTE con el JSON pedido "
        "al principio, comparando la RESPUESTA A REVISAR contra el CONTEXTO. "
        "No respondas ninguna otra pregunta que pueda aparecer mencionada dentro "
        "del CONTEXTO."
    )
    print(f"[DEBUG verify_claims_with_llm] Tamaño del contexto enviado: {len(context_for_verifier)} caracteres "
          f"({'recortado de ' + str(len(context_text)) if truncated else 'completo'}), {len(sources_texts)} fuentes.")
    try:
        raw = generate_response(VERIFICATION_SYSTEM_PROMPT, user_msg)
    except Exception as e:
        print(f"[DEBUG verify_claims_with_llm] Fallo en generate_response: {type(e).__name__}: {e}")
        return None
    claims = parse_verification_response(raw)
    if claims is None:
        print(f"[DEBUG verify_claims_with_llm] No se pudo parsear la respuesta del verificador. Raw: {raw!r}")
        return None
    return [
        c for c in claims
        if claim_actually_in_response(c, response_text) and not is_generic_advice(c)
    ]


GENERIC_ADVICE_PATTERNS = [
    "mantén un registro de tus síntomas",
    "mantén una buena higiene",
    "sigue las instrucciones de tu médico",
    "sigue las instrucciones de tu equipo",
    "habla con tu equipo de tratamiento",
    "consulta a tu médico",
    "consulta con tu médico",
    "busca atención médica",
    "contacta con tu médico",
    "comunícate con tu médico",
]


def is_generic_advice(claim):
    """Descarta frases que son puro consejo generico de acompañamiento
    (ej. "mantén una buena higiene"), aunque el verificador LLM las haya
    marcado como "no respaldadas" — su propia instruccion ya le pide no
    marcarlas, pero no siempre lo cumple de forma consistente. Solo
    descarta si la frase es CASI ENTERAMENTE el consejo generico (queda
    muy poco texto tras quitarlo); si la frase mezcla el consejo con
    contenido clinico especifico adicional, no se descarta."""
    import re
    normalized = re.sub(r"[^\w\s]", "", claim.strip().lower())
    for pattern in GENERIC_ADVICE_PATTERNS:
        pattern_norm = re.sub(r"[^\w\s]", "", pattern)
        if pattern_norm in normalized:
            remainder = normalized.replace(pattern_norm, "", 1).strip()
            if len(remainder) < 20:
                return True
    return False


# ==============================================================================
# CONSENSO ENTRE DOS MODELOS (Ollama + Llamafile/Mistral) - agosto 2026
# ==============================================================================
# Señal secundaria (complementaria a verify_claims_with_llm, que es la
# principal): genera una respuesta independiente con un segundo modelo
# para la misma pregunta y contexto, y compara si coinciden en sus
# afirmaciones. Probado hoy como prototipo en dual_model_check.py: util
# para detectar cuando un modelo añade algo que el otro no dice, pero NO
# sustituye a la verificacion contra fuentes (si los dos modelos comparten
# el mismo sesgo de entrenamiento, pueden fabricar la misma idea sin que
# esto lo note - ver seccion 8.3 del resumen del sistema).

COMPARATOR_SYSTEM_PROMPT = """Se te dan dos respuestas (A y B) generadas por dos modelos distintos a la misma pregunta clinica sobre tuberculosis, a partir del mismo contexto documental.

Identifica afirmaciones clinicas o factuales CONCRETAS que aparecen en una respuesta pero no en la otra (sintomas, causas, tratamientos, pronosticos). No cuentes frases genericas de acompanamiento ("habla con tu equipo medico") ni reformulaciones equivalentes con otras palabras.

Responde EXCLUSIVAMENTE con un JSON con este formato exacto, sin texto antes ni despues:
{"claims_only_in_a": ["..."], "claims_only_in_b": ["..."], "agreement": "alto"|"medio"|"bajo"}

"agreement" = "alto" si no hay afirmaciones discrepantes relevantes; "medio" si hay alguna discrepancia menor; "bajo" si hay afirmaciones claramente contradictorias o solo una de las dos respuestas las menciona."""


def parse_comparator_response(raw):
    """Extrae el JSON del comparador, tolerando bloques de codigo o texto
    alrededor (mismo patron que parse_verification_response)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, AttributeError):
            return None
    return None


def compare_with_llamafile(response_a, response_b):
    """Usa Ollama (via generate_response, ya validado hoy como buen juez)
    para comparar dos respuestas de modelos distintos a la misma pregunta.
    Devuelve None si falla cualquier paso (fail-open)."""
    user_prompt = f"RESPUESTA A:\n{response_a}\n\nRESPUESTA B:\n{response_b}"
    try:
        raw = generate_response(COMPARATOR_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        print(f"[DEBUG compare_with_llamafile] Fallo en generate_response: {type(e).__name__}: {e}")
        return None
    parsed = parse_comparator_response(raw)
    if parsed is None:
        print(f"[DEBUG compare_with_llamafile] No se pudo parsear la respuesta del comparador. Raw: {raw!r}")
    return parsed


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


INTENT_CLASSIFIER_SYSTEM_PROMPT = """Eres un clasificador de intencion para un chatbot clinico de tuberculosis. Tu UNICA tarea es leer el mensaje del paciente/profesional y clasificarlo en una de estas tres categorias:

"urgencia_medica": el mensaje describe sintomas fisicos que requieren atencion medica INMEDIATA, por ejemplo (no es una lista cerrada): tos con sangre abundante (hemoptisis), dificultad para respirar severa o subita, dolor en el pecho intenso, perdida de conciencia o confusion severa, reaccion alergica grave (hinchazon de cara o garganta, dificultad para tragar), fiebre muy alta con confusion.

"riesgo_autolesion": el mensaje incluye ideas o intencion de hacerse daño a si mismo o quitarse la vida.

"consulta_clinica": cualquier otra cosa — preguntas sobre efectos secundarios leves, dosis, horarios de medicacion, informacion general sobre el tratamiento, preocupaciones emocionales sin riesgo inmediato descrito.

Ante la duda entre "consulta_clinica" y una categoria de urgencia, elige la categoria de urgencia (es preferible una falsa alarma a pasar por alto una emergencia real).

Responde EXCLUSIVAMENTE con un JSON con este formato exacto, sin texto antes ni despues:
{"intencion": "urgencia_medica"|"riesgo_autolesion"|"consulta_clinica"}"""


CANNED_URGENCIA_MEDICA = (
    "Lo que describes puede ser una urgencia medica. Por favor, contacta ahora mismo "
    "con los servicios de emergencia (112 en España) o acude al servicio de urgencias "
    "mas cercano. Si estas en tratamiento por tuberculosis, informa tambien a tu equipo "
    "de tratamiento en cuanto puedas. Este chat no sustituye la atencion medica urgente."
)

CANNED_RIESGO_AUTOLESION = (
    "Lamento que estes pasando por un momento tan dificil. Por favor, no te quedes solo "
    "con esto: puedes llamar al 024 (linea de atencion a la conducta suicida, gratuita, "
    "disponible las 24 horas en España) o al 112 si hay riesgo inmediato. Tambien puedes "
    "contactar con tu equipo de tratamiento o con alguien de confianza ahora mismo. "
    "Este chat no sustituye la ayuda profesional que necesitas."
)


QUERY_EXPANSION_SYSTEM_PROMPT = """Eres un asistente que amplia consultas de busqueda para un sistema de recuperacion de informacion medica sobre tuberculosis. Dada una pregunta de un paciente o profesional, genera de 3 a 5 terminos o frases medicas relacionadas (sinonimos, nombres alternativos, terminologia clinica formal) que ayuden a encontrar documentos relevantes, aunque la persona no use esas palabras exactas.

Responde EXCLUSIVAMENTE con los terminos adicionales separados por comas, sin explicaciones ni frases completas. Ejemplo:

Pregunta: "me duele mucho la barriga"
Respuesta: dolor abdominal, molestias gastrointestinales, dolor epigastrico

No repitas palabras que ya aparecen en la pregunta original. No inventes sintomas ni farmacos que no esten relacionados con la pregunta."""


def expand_query(original_query, timeout=15):
    """Genera terminos relacionados para ampliar la consulta de
    recuperacion (mejora el recall cuando la persona no usa la
    terminologia clinica exacta de las guias). Fail-open: devuelve la
    consulta original sin cambios si falla, si la respuesta esta vacia,
    o si es sospechosamente larga (señal de que el modelo no siguio el
    formato pedido)."""
    try:
        raw = generate_response(QUERY_EXPANSION_SYSTEM_PROMPT, original_query)
        terminos = raw.strip()
        if not terminos or len(terminos) > 300:
            return original_query
        return f"{original_query} {terminos}"
    except Exception:
        return original_query


def classify_intent(message, timeout=15):
    """Clasifica la intencion del mensaje ANTES de cualquier recuperacion
    documental (independiente de si ChromaDB encuentra algo relevante).
    Fail-open: si falla, devuelve "consulta_clinica" (el comportamiento
    normal de siempre, sin regresion respecto a como funcionaba antes de
    añadir este clasificador)."""
    try:
        raw = generate_response(INTENT_CLASSIFIER_SYSTEM_PROMPT, message)
        parsed = parse_comparator_response(raw)
        if parsed and parsed.get("intencion") in ("urgencia_medica", "riesgo_autolesion"):
            return parsed["intencion"]
    except Exception:
        pass
    return "consulta_clinica"


CLINICAL_RED_FLAG_RULES = [
    {
        "id": "ethambutol_visual",
        "drugs": ["etambutol", "ethambutol"],
        "symptoms": ["borros", "veo mal", "colores diferentes", "no veo bien",
                     "pérdida de visión", "perdida de vision", "vista mal", "veo raro"],
    },
    {
        "id": "isoniazid_neuropathy",
        "drugs": ["isoniazida", "isoniacida", "isoniazid"],
        "symptoms": ["hormigueo", "entumecimiento", "quemazón", "quemazon",
                     "pies dormidos", "manos dormidas", "pies dormidos"],
    },
    {
        "id": "hepatotoxicity",
        "drugs": [],
        "symptoms": ["orina oscura", "orina marrón", "orina marron", "heces claras",
                     "piel amarilla", "ojos amarillos", "ictericia"],
    },
    {
        "id": "cardiac_symptoms",
        "drugs": [],
        "symptoms": ["me desmayé", "me desmaye", "perdida de conciencia",
                     "pérdida de conciencia", "palpitaciones fuertes"],
    },
    {
        "id": "hemoptysis_severe",
        "drugs": [],
        "symptoms": ["tos con sangre", "toso sangre", "tosiendo sangre", "tosiendo con sangre",
                     "toser sangre", "sangre al toser", "escupo sangre", "escupir sangre",
                     "sangre en el esputo", "esputo con sangre"],
    },
    {
        "id": "medication_overdose",
        "drugs": [],
        "symptoms": ["me tomé el doble", "me tome el doble", "doble dosis",
                     "dos pastillas en vez de una", "sobredosis"],
    },
]


def check_deterministic_red_flags(message):
    """Comprueba patrones de riesgo YA CONOCIDOS mediante palabras clave,
    sin depender de ningun LLM (instantaneo y 100% predecible para estos
    casos concretos). Complementa a classify_intent(), que sigue
    cubriendo framings nuevos o menos comunes.

    Devuelve el id de la regla si hay coincidencia, o None.

    LIMITACION CONOCIDA Y ACEPTADA: no detecta negaciones ("no tomo
    isoniazida" activaria igual la regla si menciona el sintoma). Se
    acepta a proposito: el coste de una falsa alarma (mensaje de
    urgencia de mas) es mucho menor que el de pasar por alto una
    emergencia real — mismo criterio que classify_intent()."""
    normalized = message.lower()
    for rule in CLINICAL_RED_FLAG_RULES:
        symptom_match = any(s in normalized for s in rule["symptoms"])
        if not symptom_match:
            continue
        if rule["drugs"] and not any(d in normalized for d in rule["drugs"]):
            continue
        return rule["id"]
    return None


@app.post("/api/chat")
def chat(request: ChatRequest):
    red_flag = check_deterministic_red_flags(request.message)
    if red_flag:
        log_usage_pattern("/api/chat", f"red_flag_{red_flag}", question=request.message)
        return {
            "response": CANNED_URGENCIA_MEDICA,
            "sources": [],
            "coverage": f"red_flag_{red_flag}",
        }

    intencion = classify_intent(request.message)
    if intencion == "urgencia_medica":
        log_usage_pattern("/api/chat", "urgencia_medica_general", question=request.message)
        return {"response": CANNED_URGENCIA_MEDICA, "sources": [], "coverage": "urgencia_medica_general"}
    if intencion == "riesgo_autolesion":
        log_usage_pattern("/api/chat", "riesgo_autolesion", question=request.message)
        return {"response": CANNED_RIESGO_AUTOLESION, "sources": [], "coverage": "riesgo_autolesion"}

    retrieval_query = build_retrieval_query(request.message, request.history)
    retrieval_query = expand_query(retrieval_query)
    fragments, metadatas, distances = retrieve(retrieval_query, request.top_k)
    has_keyword = is_tb_related(request.message)

    fallback_used = False
    if not is_relevant(fragments, distances, has_keyword):
        fb_fragments, fb_metadatas, fb_info = query_sota_fallback(retrieval_query)

        if fb_info and isinstance(fb_info, dict) and fb_info.get("alert"):
            log_usage_pattern("/api/chat", "alerta_clinica", question=request.message)
            return {
                "response": " ".join(fb_info["alert"]),
                "sources": [],
                "coverage": "alerta_clinica",
            }

        if fb_fragments:
            fragments, metadatas = fb_fragments, fb_metadatas
            distances = []
            fallback_used = True
        else:
            log_usage_pattern("/api/chat", "sin_cobertura", question=request.message)
            return {
                "response": "No encuentro esta informacion en los documentos disponibles.",
                "sources": [],
            }

    context_parts = []
    sources_used = []
    for frag, meta in zip(fragments, metadatas):
        page_part = ", pagina: " + str(meta["page"]) if meta.get("page") is not None else ""
        context_parts.append(
            "[Fuente: " + meta["source"] + ", categoria: " + meta["category"] + page_part + "]\n" + frag
        )
        sources_used.append({
            "source": meta["source"],
            "category": meta["category"],
            "page": meta.get("page"),
            "text": frag,
        })

    # Bibliografia cientifica verificada adicional (PubMed + Europe PMC,
    # confirmado por PubTator3, validado por CrossRef — ver
    # tbc-master-database/). Señal complementaria: no sustituye a las
    # fuentes clinicas de arriba (FAQ/PDF), solo añade literatura reciente
    # cuando esta disponible. Fail-open: si el servicio (puerto 8002) no
    # responde, sigue funcionando igual que hasta ahora, sin ella.
    bibliography_results = query_master_bibliography(request.message, limit=2)
    for bib in bibliography_results:
        if bib.get("retraction_status") != "ninguna":
            continue
        cite = f"{bib.get('journal') or 'revista desconocida'} ({bib.get('year') or 's.f.'})"
        context_parts.append(
            f"[Fuente: bibliografia cientifica verificada, {cite}]\n"
            f"{bib.get('title', '')}\n{bib.get('abstract', '')}"
        )
        sources_used.append({
            "source": f"PubMed/Europe PMC - {cite}",
            "category": "bibliografia_cientifica",
            "page": None,
            "text": bib.get("abstract") or bib.get("title", ""),
            "doi": bib.get("doi"),
            "pmid": bib.get("pmid"),
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
    if fallback_used and sources_used:
        result["coverage"] = "complementaria"
    elif distances and sources_used:
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
            "fallback_used": fallback_used,
        }

    if request.debug and sources_used:
        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims

        response_b = query_llamafile_response(context_text, request.message)
        if response_b is not None:
            dual_model_comparison = compare_with_llamafile(final_response, response_b)
            if dual_model_comparison is not None:
                result.setdefault("debug_info", {})["dual_model_comparison"] = {
                    "response_b": response_b,
                    **dual_model_comparison,
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

    fallback_used = False
    if not is_relevant(fragments, distances, has_keyword):
        fb_fragments, fb_metadatas, fb_info = query_sota_fallback(retrieval_query)

        if fb_info and isinstance(fb_info, dict) and fb_info.get("alert"):
            log_usage_pattern("/api/patient-chat", "alerta_clinica", lang=request.lang)
            alert_text = " ".join(fb_info["alert"])
            return {"response": f"{alert_text} {canned_no_info}"}

        if fb_fragments:
            fragments, metadatas = fb_fragments, fb_metadatas
            distances = []
            fallback_used = True
        else:
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
            "fallback_used": fallback_used,
        }

        if fragments:
            llm_unsupported_claims = verify_claims_with_llm(fragments, final_response)
            if llm_unsupported_claims is not None:
                result["debug_info"]["llm_unsupported_claims"] = llm_unsupported_claims

            response_b = query_llamafile_response(context_text, request.message)
            if response_b is not None:
                dual_model_comparison = compare_with_llamafile(final_response, response_b)
                if dual_model_comparison is not None:
                    result["debug_info"]["dual_model_comparison"] = {
                        "response_b": response_b,
                        **dual_model_comparison,
                    }

    # Cobertura interna, solo para el registro de patrones de uso (no se
    # muestra al paciente, igual que las fuentes: aqui usamos los mismos
    # umbrales que en /api/chat para mantener las estadisticas comparables
    # entre ambos endpoints).
    if fallback_used:
        internal_coverage = "complementaria"
    elif distances:
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
    <a class="card" href="http://127.0.0.1:8090" target="_blank">
      <span class="tag clinic">Sistema</span>
      <h2>Panel TBC-IA</h2>
      <p>Estat en temps real dels set serveis (Ollama, motor complementari, Llamafile, n8n, bibliografia...).</p>
      <div class="status"><span class="dot" id="panel-dot" style="background:#888;"></span><span id="panel-text">Comprovant...</span></div>
    </a>
  </div>

  <div class="biblio-search-section" style="max-width:900px;margin:40px auto;padding:0 20px;">
    <h2 style="margin-bottom:12px;">Cerca a la bibliografia verificada</h2>
    <div style="display:flex;gap:8px;margin-bottom:16px;">
      <input id="biblio-query" type="text" placeholder="p.ex. isoniazid resistance"
             style="flex:1;padding:10px;border-radius:6px;border:1px solid #ccc;font-size:14px;"
             onkeydown="if(event.key==='Enter') searchBiblio()">
      <button onclick="searchBiblio()"
              style="padding:10px 20px;border-radius:6px;border:none;background:#1F4B4C;color:white;cursor:pointer;font-size:14px;">
        Cercar (base verificada)
      </button>
      <button onclick="searchBiblioLive()"
              style="padding:10px 20px;border-radius:6px;border:1px solid #1F4B4C;background:white;color:#1F4B4C;cursor:pointer;font-size:14px;">
        Cercar en viu a PubMed
      </button>
    </div>
    <div id="biblio-results"></div>
  </div>

  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
  <script>
    fetch('/api/panel-status').then(r => r.json()).then(d => {
      const dot = document.getElementById('panel-dot');
      const text = document.getElementById('panel-text');
      if (d.connected) {
        dot.style.background = '#4ade80';
        text.textContent = 'Panel connectat';
      } else {
        dot.style.background = '#f87171';
        text.textContent = 'Panel no connectat';
      }
    }).catch(() => {
      document.getElementById('panel-text').textContent = 'Panel no connectat';
    });

    let currentBiblioResults = [];

    function articleCardsHtml(results, live) {
      if (!results || !results.length) return '';
      const badge = live
        ? '<span style="background:#fef3c7;color:#92400e;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">EN VIU · SENSE VERIFICAR</span>'
        : '<span style="background:#dcfce7;color:#166534;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">VERIFICAT</span>';
      return results.map((r, i) => `
        <div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:10px;">
          <strong>${r.title || ''}</strong>${badge}<br>
          <span style="color:#666;font-size:13px;">${r.journal || 'revista desconeguda'} (${r.year || 's.f.'}) — PMID: ${r.pmid || '-'}</span>
          <p style="font-size:14px;margin-top:8px;" id="biblio-abstract-${i}">${(r.abstract || '').slice(0, 300)}${(r.abstract || '').length > 300 ? '...' : ''}</p>
          <button onclick="translateCard(${i})"
                  style="font-size:12px;padding:4px 10px;border-radius:6px;border:1px solid #1F4B4C;background:white;color:#1F4B4C;cursor:pointer;margin-bottom:6px;">
            Traduir al castella
          </button>
          <div id="biblio-translated-${i}" style="font-size:14px;color:#333;font-style:italic;margin-bottom:6px;"></div>
          ${r.doi ? `<a href="https://doi.org/${r.doi}" target="_blank">DOI: ${r.doi}</a>` : ''}
        </div>
      `).join('');
    }

    function aempsCardHtml(r) {
      if (!r) return '';
      return `
        <div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:10px;">
          <strong>${r.nombre || ''}</strong>
          <span style="background:#dcfce7;color:#166534;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">VERIFICAT · CIMA AEMPS</span>
          <br><span style="color:#666;font-size:13px;">${r.laboratorio || ''} — nº registre ${r.nregistro || '-'}</span>
          <p style="font-size:14px;margin-top:8px;"><strong>Contraindicacions:</strong> ${r.contraindicaciones || 'no disponible'}</p>
          <p style="font-size:14px;"><strong>Interaccions:</strong> ${r.interacciones || 'no disponible'}</p>
          <p style="font-size:14px;"><strong>Reaccions adverses:</strong> ${r.reacciones_adversas || 'no disponible'}</p>
        </div>
      `;
    }

    function renderBiblioResults(results, resultsDiv, live) {
      currentBiblioResults = results || [];
      const html = articleCardsHtml(results, live);
      resultsDiv.innerHTML = html || '<p>Sense resultats.</p>';
    }

    async function translateCard(i) {
      const div = document.getElementById('biblio-translated-' + i);
      const r = currentBiblioResults[i];
      if (!r || !r.abstract) {
        div.textContent = 'No hi ha text per traduir.';
        return;
      }
      div.textContent = 'Traduint (pot trigar uns segons, es fa amb el model local)...';
      try {
        const resp = await fetch('/api/translate?text=' + encodeURIComponent(r.abstract));
        const data = await resp.json();
        div.textContent = data.error ? 'Error en la traduccio.' : data.translated;
      } catch (e) {
        div.textContent = 'Error en la traduccio.';
      }
    }

    async function searchBiblio() {
      const q = document.getElementById('biblio-query').value.trim();
      const resultsDiv = document.getElementById('biblio-results');
      if (!q) return;
      resultsDiv.innerHTML = '<p>Cercant a la base verificada (bibliografia + CIMA)...</p>';
      try {
        const [biblioResp, aempsResp] = await Promise.all([
          fetch('/api/bibliography-search?query=' + encodeURIComponent(q) + '&limit=5'),
          fetch('/api/aemps-search?query=' + encodeURIComponent(q)),
        ]);
        const biblioData = await biblioResp.json();
        const aempsData = await aempsResp.json();

        currentBiblioResults = biblioData.results || [];
        const html = aempsCardHtml(aempsData.result) + articleCardsHtml(currentBiblioResults, false);
        resultsDiv.innerHTML = html || '<p>Sense resultats a la base verificada (bibliografia ni CIMA).</p>';
      } catch (e) {
        resultsDiv.innerHTML = '<p>Error consultant la base verificada.</p>';
      }
    }

    async function searchBiblioLive() {
      const q = document.getElementById('biblio-query').value.trim();
      const resultsDiv = document.getElementById('biblio-results');
      if (!q) return;
      resultsDiv.innerHTML = '<p>Cercant en viu a PubMed (pot trigar unes segons)...</p>';
      try {
        const resp = await fetch('/api/bibliography-search-live?query=' + encodeURIComponent(q) + '&limit=5');
        const data = await resp.json();
        renderBiblioResults(data.results, resultsDiv, true);
      } catch (e) {
        resultsDiv.innerHTML = '<p>Error consultant PubMed en viu.</p>';
      }
    }

    async function searchAemps() {
      const q = document.getElementById('biblio-query').value.trim();
      const resultsDiv = document.getElementById('biblio-results');
      if (!q) return;
      resultsDiv.innerHTML = '<p>Cercant a CIMA (AEMPS)...</p>';
      try {
        const resp = await fetch('/api/aemps-search?query=' + encodeURIComponent(q));
        const data = await resp.json();
        if (!data.result) {
          resultsDiv.innerHTML = '<p>No shan trobat medicaments amb aquest nom a CIMA.</p>';
          return;
        }
        const r = data.result;
        resultsDiv.innerHTML = `
          <div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:10px;">
            <strong>${r.nombre || ''}</strong>
            <span style="background:#e0e7ff;color:#3730a3;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">CIMA · FITXA OFICIAL AEMPS</span>
            <br><span style="color:#666;font-size:13px;">${r.laboratorio || ''} — nº registre ${r.nregistro || '-'}</span>
            <p style="font-size:14px;margin-top:8px;"><strong>Contraindicacions:</strong> ${r.contraindicaciones || 'no disponible'}</p>
            <p style="font-size:14px;"><strong>Interaccions:</strong> ${r.interacciones || 'no disponible'}</p>
            <p style="font-size:14px;"><strong>Reaccions adverses:</strong> ${r.reacciones_adversas || 'no disponible'}</p>
          </div>
        `;
      } catch (e) {
        resultsDiv.innerHTML = '<p>Error consultant CIMA.</p>';
      }
    }
  </script>
</body>
</html>
"""
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
def bibliography_search(query: str, limit: int = 5):
    """Busca en la bibliografia verificada (tbc_master.db) directamente,
    sin pasar por el puerto 8002 (reutiliza query_master_bibliography, ya
    usada en /api/chat). Fail-open: devuelve lista vacia si falla."""
    try:
        results = query_master_bibliography(query, limit=limit)
    except Exception:
        results = []
    results = [r for r in results if r.get("retraction_status") == "ninguna"]
    return {"query": query, "results": results}


@app.get("/api/bibliography-search-live")
def bibliography_search_live(query: str, limit: int = 5):
    """Busca en vivo directamente en PubMed, SIN verificacion de PubTator3
    ni validacion de CrossRef ni deteccion de retracciones (a diferencia
    de /api/bibliography-search). Util cuando la base local no tiene
    resultados para una consulta concreta. Fail-open: lista vacia si falla."""
    try:
        results = search_pubmed_live(query, max_results=limit)
    except Exception:
        results = []
    return {"query": query, "results": results}


@app.get("/api/translate")
def translate_text(text: str):
    """Traduce un texto (resumen de un articulo) al castellano usando
    Ollama (100% local, sin servicios externos de traduccion). Fail-open:
    devuelve error=True si falla."""
    system_prompt = (
        "Traduce el siguiente texto cientifico-medico (resumen de un articulo "
        "sobre tuberculosis) al castellano. Manten la terminologia clinica "
        "precisa. Responde EXCLUSIVAMENTE con la traduccion, sin comentarios "
        "ni explicaciones adicionales."
    )
    try:
        translated = generate_response(system_prompt, text)
        return {"translated": translated, "error": False}
    except Exception:
        return {"translated": None, "error": True}


@app.get("/api/aemps-search")
def aemps_search(query: str):
    """Busca un medicamento en CIMA (AEMPS) y devuelve su ficha tecnica
    oficial: contraindicaciones, interacciones, reacciones adversas.
    Fail-open: result=None si no se encuentra o falla la consulta."""
    try:
        result = get_drug_safety_info(query)
    except Exception:
        result = None
    return {"query": query, "result": result}


app.mount("/guides", StaticFiles(directory=GUIDES_DIR, html=True), name="guides")
app.mount("/patient", StaticFiles(directory=PATIENT_DIR, html=True), name="patient")
