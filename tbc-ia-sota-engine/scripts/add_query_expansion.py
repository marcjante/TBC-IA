#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade ampliacion de consultas (query expansion) justo despues de construir
retrieval_query y antes de llamar a retrieve(). Genera terminos medicos
relacionados (sinonimos, nombres alternativos, terminologia clinica
formal) usando Ollama, para mejorar la recuperacion cuando el paciente
no usa las mismas palabras que las guias clinicas (ej. "me duele la
barriga" -> añade "dolor abdominal, molestias gastrointestinales").

Fail-open: si falla o la respuesta no tiene sentido (vacia o
sospechosamente larga), se usa la consulta original sin cambios — nunca
bloquea ni degrada el flujo normal.

Uso:
    python3 add_query_expansion.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    if intencion == "riesgo_autolesion":
        log_usage_pattern("/api/chat", "riesgo_autolesion", question=request.message)
        return {"response": CANNED_RIESGO_AUTOLESION, "sources": [], "coverage": "riesgo_autolesion"}

    retrieval_query = build_retrieval_query(request.message, request.history)'''

NEW = '''    if intencion == "riesgo_autolesion":
        log_usage_pattern("/api/chat", "riesgo_autolesion", question=request.message)
        return {"response": CANNED_RIESGO_AUTOLESION, "sources": [], "coverage": "riesgo_autolesion"}

    retrieval_query = build_retrieval_query(request.message, request.history)
    retrieval_query = expand_query(retrieval_query)'''

FUNCTION_ANCHOR = '''def classify_intent(message, timeout=15):'''

FUNCTION_ADDITION = '''QUERY_EXPANSION_SYSTEM_PROMPT = """Eres un asistente que amplia consultas de busqueda para un sistema de recuperacion de informacion medica sobre tuberculosis. Dada una pregunta de un paciente o profesional, genera de 3 a 5 terminos o frases medicas relacionadas (sinonimos, nombres alternativos, terminologia clinica formal) que ayuden a encontrar documentos relevantes, aunque la persona no use esas palabras exactas.

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


def classify_intent(message, timeout=15):'''


def apply_patch(path, old, new, label):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if new in content:
        print(f"  {label}: ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(old)
    if count == 0:
        print(f"  {label}: ABORTADO, no se encontró el bloque esperado. No se ha escrito nada.")
        sys.exit(1)
    if count > 1:
        print(f"  {label}: ABORTADO, el bloque aparece {count} veces (debería ser único). No se ha escrito nada.")
        sys.exit(1)

    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  {label}: aplicado correctamente.")


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_query_expansion.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    apply_patch(path, FUNCTION_ANCHOR, FUNCTION_ADDITION, "funcion expand_query")
    apply_patch(path, OLD, NEW, "llamada a expand_query en /api/chat")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
