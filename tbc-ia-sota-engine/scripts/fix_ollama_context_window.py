#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige la causa real (no un parche superficial) de la lentitud extrema
y las fabricaciones detectadas el 23 de agosto de 2026: generate_response()
no especificaba num_ctx, asi que Ollama usaba el valor por defecto del
modelo (4096 tokens, confirmado con `ollama ps`). Con hybrid_retrieve()
trayendo mas fuentes por pregunta, el contexto real ya alcanzaba ~17.000
caracteres (~4.400 tokens) en pruebas reales — superando el limite de
4096 ANTES de sumar la pregunta, el historial y las instrucciones del
sistema.

Esto es una causa plausible de ambos problemas observados:
  - Lentitud: Ollama hace un trabajo interno costoso ("context shifting")
    cuando la entrada no cabe en la ventana configurada.
  - Fabricaciones: si el contexto real se corta o se maneja mal
    internamente, el modelo rellena huecos con conocimiento propio en
    vez de las fuentes reales.

Como generate_response() es el envoltorio UNICO usado por todas las
llamadas (clasificador, ampliacion, generacion, verificacion,
comparacion — ver el comentario "Fase 7 de la auditoria" ya presente en
el archivo), este cambio se aplica a todas ellas de una vez.

Uso:
    python3 fix_ollama_context_window.py "/ruta/a/backend/llm.py"
"""

import sys

OLD = '''def generate_response(system_prompt, user_prompt):
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "temperature": 0.1,
            "top_p": 0.9,
        },
    )
    return response["message"]["content"]'''

NEW = '''def generate_response(system_prompt, user_prompt):
    # num_ctx: sin especificar, Ollama usaba el valor por defecto del
    # modelo (4096 tokens, confirmado con `ollama ps`). Con
    # hybrid_retrieve() (agosto 2026) el contexto real ya supera esa
    # cifra en preguntas normales (~17.000 caracteres ~ 4.400 tokens,
    # antes de sumar pregunta/historial/sistema), lo que causaba
    # lentitud extrema y citas inventadas cuando el contexto no cabia.
    # 8192 da margen razonable sin disparar el uso de memoria en exceso.
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "temperature": 0.1,
            "top_p": 0.9,
            "num_ctx": 8192,
        },
    )
    return response["message"]["content"]'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 fix_ollama_context_window.py <ruta a backend/llm.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "num_ctx" in content:
        print("Ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(OLD)
    if count == 0:
        print("ABORTADO: no se encontró el bloque esperado. No se ha escrito nada.")
        sys.exit(1)
    if count > 1:
        print(f"ABORTADO: el bloque aparece {count} veces (debería ser único). No se ha escrito nada.")
        sys.exit(1)

    content = content.replace(OLD, NEW, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Aplicado correctamente: {path}")


if __name__ == "__main__":
    main()
