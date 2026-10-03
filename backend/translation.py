"""
TBC-AI - backend/translation.py

Traduccion local (Ollama) para el chat de pacientes, revision de seguridad
clinica de octubre 2026:

- C4: los filtros de seguridad (signos de alarma, fugas de conocimiento
  general, "no lo se", interacciones) solo entienden castellano. Las
  preguntas en catalan, arabe o urdu se traducen al castellano ANTES de
  clasificarlas, buscar y generar; la respuesta se genera y verifica en
  castellano y se traduce al final.
- A6: la traduccion final se acepta solo si conserva exactamente las mismas
  cifras (dosis, duraciones, telefonos) que el original.

Nada sale del ordenador: todo se hace con el modelo local.
"""

import logging

from backend.clinical_rules import numbers_preserved
from backend.languages import LANG_NAMES
from backend.llm import generate_response

logger = logging.getLogger("tbc.translation")

_TO_SPANISH_PROMPT = (
    "Traduce al castellano el mensaje de un paciente. Conserva exactamente el sentido, "
    "los sintomas, los nombres de medicamentos y todas las cifras. No respondas al "
    "mensaje ni añadas nada: devuelve EXCLUSIVAMENTE la traduccion."
)

_FROM_SPANISH_PROMPT = (
    "Traduce al {lang} el texto de un asistente sanitario dirigido a un paciente. "
    "Usa frases sencillas. Conserva EXACTAMENTE todas las cifras (dosis, numero de "
    "meses, semanas o dias, telefonos como 112 o 024) con los mismos digitos, y los "
    "nombres de los medicamentos. No añadas, quites ni resumas informacion. Devuelve "
    "EXCLUSIVAMENTE la traduccion."
)

_ABSTRACT_PROMPT = (
    "Traduce el siguiente texto cientifico-medico (resumen de un articulo sobre "
    "tuberculosis) al castellano. Manten la terminologia clinica precisa y todas las "
    "cifras. Responde EXCLUSIVAMENTE con la traduccion, sin comentarios."
)


def translate_to_spanish(text, lang):
    """Traduce el mensaje del paciente al castellano. Si lang ya es "es"
    devuelve el texto tal cual. Devuelve None si la traduccion falla (quien
    llama debe seguir aplicando los filtros sobre el texto original)."""
    if lang == "es" or not text.strip():
        return text
    try:
        translated = generate_response(_TO_SPANISH_PROMPT, text).strip()
    except Exception as e:
        logger.warning("translate_to_spanish: fallo del LLM (%s)", type(e).__name__)
        return None
    return translated or None


def translate_from_spanish(text, lang):
    """Traduce una respuesta en castellano al idioma del paciente. Devuelve
    None si falla o si la traduccion no conserva las cifras del original."""
    if lang == "es":
        return text
    try:
        translated = generate_response(
            _FROM_SPANISH_PROMPT.format(lang=LANG_NAMES.get(lang, "castellano")), text
        ).strip()
    except Exception as e:
        logger.warning("translate_from_spanish: fallo del LLM (%s)", type(e).__name__)
        return None
    if not translated:
        return None
    if not numbers_preserved(text, translated):
        logger.warning("translate_from_spanish: la traduccion altera cifras; se descarta")
        return None
    return translated


def translate_abstract(text):
    """Traduccion de resumenes de articulos (portada, uso profesional)."""
    return generate_response(_ABSTRACT_PROMPT, text)
