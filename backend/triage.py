"""
TBC-AI - backend/triage.py

Triaje previo a la recuperacion (extraido de main.py en la revision de
seguridad clinica de octubre 2026): clasificador de intencion por LLM,
expansion de la consulta y mensajes fijos de urgencia/autolesion.
Las reglas deterministas de signos de alarma viven en clinical_rules.py.
"""

import logging
import time

from backend.llm import generate_response
from backend.verification import parse_comparator_response

logger = logging.getLogger("tbc.triage")


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

IMPORTANTE: gran parte de las guias clinicas de referencia (OMS, CDC, ECDC) estan escritas en ingles. Si la pregunta esta en español y trata un tema clinico que probablemente este documentado en esas guias (tratamiento, farmacos, dosis, efectos adversos, duracion), incluye TAMBIEN 1-2 terminos clinicos equivalentes en ingles (ej. "6-month regimen", "rifampicin", "adverse reactions") ademas de los terminos en español, para poder encontrar el texto original si la busqueda por palabras exactas lo necesita.

Responde EXCLUSIVAMENTE con los terminos adicionales separados por comas, sin explicaciones ni frases completas. Ejemplo:

Pregunta: "cuanto dura el tratamiento de tuberculosis"
Respuesta: duracion del tratamiento, pauta terapeutica, 6-month regimen, treatment duration

No repitas palabras que ya aparecen en la pregunta original. No inventes sintomas ni farmacos que no esten relacionados con la pregunta."""


def expand_query(original_query):
    """Genera terminos relacionados para ampliar la consulta de recuperacion.
    Fail-open (solo afecta a la busqueda, no a la seguridad): devuelve la
    consulta original si falla o si la respuesta es sospechosamente larga."""
    _t0 = time.time()
    try:
        raw = generate_response(QUERY_EXPANSION_SYSTEM_PROMPT, original_query)
        logger.info("expand_query: %.1fs", time.time() - _t0)
    except Exception as e:
        logger.warning("expand_query: fallo del LLM (%s)", type(e).__name__)
        return original_query
    terminos = raw.strip()
    if not terminos or len(terminos) > 300:
        return original_query
    return f"{original_query} {terminos}"


def classify_intent(message):
    """Clasifica la intencion del mensaje ANTES de cualquier recuperacion.

    Devuelve (intencion, ok). Revision de seguridad clinica (octubre 2026,
    A4): antes, si el clasificador fallaba, se devolvia "consulta_clinica"
    en silencio (fallo abierto). Ahora ok=False permite a quien llama añadir
    siempre una linea de derivacion a la respuesta."""
    _t0 = time.time()
    try:
        raw = generate_response(INTENT_CLASSIFIER_SYSTEM_PROMPT, message)
        logger.info("classify_intent: %.1fs", time.time() - _t0)
    except Exception as e:
        logger.warning("classify_intent: fallo del LLM (%s)", type(e).__name__)
        return "consulta_clinica", False
    parsed = parse_comparator_response(raw)
    if not parsed or parsed.get("intencion") not in ("urgencia_medica", "riesgo_autolesion", "consulta_clinica"):
        logger.warning("classify_intent: respuesta no interpretable")
        return "consulta_clinica", False
    return parsed["intencion"], True


# Plantillas para el chat PROFESIONAL (B1): un profesional que pregunta por un
# signo de alarma suele estar consultando sobre un paciente, no viviendo la
# urgencia. En vez de cortar con el mensaje del 112, se antepone un aviso y se
# responde igualmente con las guias.
PRO_ALERTA_SIGNO_ALARMA = (
    "⚠️ Esta consulta menciona un signo de alarma. Si un paciente presenta ahora "
    "esta clinica, requiere valoracion urgente (112 / servicio de urgencias); no "
    "esperes a esta respuesta para actuar.\n\n"
)
PRO_ALERTA_AUTOLESION = (
    "⚠️ Esta consulta menciona riesgo de autolesion. Si hay riesgo inmediato: 112. "
    "Linea de atencion a la conducta suicida: 024 (gratuita, 24 h).\n\n"
)
