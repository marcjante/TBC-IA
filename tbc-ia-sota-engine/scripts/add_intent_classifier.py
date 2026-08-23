#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade un clasificador GENERAL de intencion al principio de /api/chat, que
se ejecuta ANTES de la recuperacion documental (independiente de si
ChromaDB encuentra algo relevante o no). Complementa al sistema de
alertas existente (alerta_clinica, basado en palabras clave de farmacos
concretos como etambutol+vision, dentro del fallback del motor
complementario) — no lo sustituye.

Distingue tres categorias:
  - urgencia_medica: sintomas fisicos que requieren atencion inmediata
    (hemoptisis, dificultad respiratoria severa, dolor toracico, reaccion
    alergica grave, perdida de conciencia)
  - riesgo_autolesion: ideas de hacerse daño a si mismo — requiere
    recursos de crisis especificos, no solo indicar "ve a urgencias"
  - consulta_clinica: todo lo demas, sigue el flujo normal

Las respuestas para los dos casos de urgencia son TEXTO FIJO (no
generado por el LLM), para garantizar fiabilidad en algo tan sensible.
Fail-open: si el clasificador falla, se trata como consulta_clinica (el
comportamiento normal de siempre, sin regresion).

Uso:
    python3 add_intent_classifier.py "/ruta/a/backend/main.py"
"""

import sys

ANCHOR = '''@app.post("/api/chat")
def chat(request: ChatRequest):
    retrieval_query = build_retrieval_query(request.message, request.history)'''

REPLACEMENT = '''INTENT_CLASSIFIER_SYSTEM_PROMPT = """Eres un clasificador de intencion para un chatbot clinico de tuberculosis. Tu UNICA tarea es leer el mensaje del paciente/profesional y clasificarlo en una de estas tres categorias:

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


@app.post("/api/chat")
def chat(request: ChatRequest):
    intencion = classify_intent(request.message)
    if intencion == "urgencia_medica":
        log_usage_pattern("/api/chat", "urgencia_medica_general", question=request.message)
        return {"response": CANNED_URGENCIA_MEDICA, "sources": [], "coverage": "urgencia_medica_general"}
    if intencion == "riesgo_autolesion":
        log_usage_pattern("/api/chat", "riesgo_autolesion", question=request.message)
        return {"response": CANNED_RIESGO_AUTOLESION, "sources": [], "coverage": "riesgo_autolesion"}

    retrieval_query = build_retrieval_query(request.message, request.history)'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_intent_classifier.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "classify_intent" in content:
        print("Ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(ANCHOR)
    if count == 0:
        print("ABORTADO: no se encontró el bloque esperado. No se ha escrito nada.")
        sys.exit(1)
    if count > 1:
        print(f"ABORTADO: el bloque aparece {count} veces (debería ser único). No se ha escrito nada.")
        sys.exit(1)

    content = content.replace(ANCHOR, REPLACEMENT, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Aplicado correctamente: {path}")


if __name__ == "__main__":
    main()
