#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prueba aislada de query_llamafile_response() y del comparador para ver
exactamente que devuelven y si hay alguna excepcion oculta.

Ejecutar desde la carpeta TBC IA, con el venv activado:
    cd ~/Desktop/"TBC IA"
    source venv/bin/activate
    python3 diagnostico_dual_model.py
"""

import sys
sys.path.insert(0, ".")

from backend.rag import query_llamafile_response
from backend.llm import generate_response
import json
import re

context_text = (
    "P: Desde el diagnostico no puedo dormir por la ansiedad, que hago?\n"
    "R: La ansiedad es un sintoma comun en personas con tuberculosis."
)
question = "Me siento muy solo desde que empezo todo esto"

print("=== Paso 1: query_llamafile_response ===")
try:
    response_b = query_llamafile_response(context_text, question, timeout=90)
    print("Tipo:", type(response_b))
    print("Contenido:", repr(response_b))
except Exception as e:
    print("EXCEPCION NO CAPTURADA:", type(e).__name__, e)
    response_b = None

if response_b is None:
    print("\nresponse_b es None -> aqui se corta la cadena, no se llega al comparador.")
    sys.exit(0)

print("\n=== Paso 2: comparador (usando generate_response / Ollama) ===")
COMPARATOR_SYSTEM_PROMPT = """Se te dan dos respuestas (A y B) generadas por dos modelos distintos a la misma pregunta clinica sobre tuberculosis, a partir del mismo contexto documental.

Identifica afirmaciones clinicas o factuales CONCRETAS que aparecen en una respuesta pero no en la otra (sintomas, causas, tratamientos, pronosticos). No cuentes frases genericas de acompanamiento ni reformulaciones equivalentes.

Responde EXCLUSIVAMENTE con un JSON con este formato exacto, sin texto antes ni despues:
{"claims_only_in_a": ["..."], "claims_only_in_b": ["..."], "agreement": "alto"|"medio"|"bajo"}
"""

response_a = "Lo siento mucho, es normal sentirse solo."
user_prompt = f"RESPUESTA A:\n{response_a}\n\nRESPUESTA B:\n{response_b}"

try:
    raw = generate_response(COMPARATOR_SYSTEM_PROMPT, user_prompt)
    print("Raw devuelto por generate_response:")
    print(repr(raw))
except Exception as e:
    print("EXCEPCION NO CAPTURADA en generate_response:", type(e).__name__, e)
    sys.exit(0)

print("\n=== Paso 3: parseo del JSON ===")
cleaned = raw.strip()
if cleaned.startswith("```"):
    cleaned = cleaned.strip("`")
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:]
    cleaned = cleaned.strip()

try:
    parsed = json.loads(cleaned)
    print("Parseo directo OK:", parsed)
except Exception as e:
    print("Parseo directo fallo:", e)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            print("Parseo con regex OK:", parsed)
        except Exception as e2:
            print("Parseo con regex TAMBIEN fallo:", e2)
    else:
        print("No se encontro ningun bloque {...} en el texto.")
