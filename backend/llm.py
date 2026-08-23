"""
TBC-AI - backend/llm.py

Wrapper unico para las llamadas de generacion a Ollama. Ambos endpoints de
chat usaban la misma llamada (mismo modelo, misma temperatura) de forma
duplicada; aqui queda en un solo sitio.

FASE 7 de la auditoria: extraido de main.py, mismos parametros
(temperature=0.1, top_p=0.9) que ya se usaban en produccion.
"""

import ollama

from backend.config import CHAT_MODEL


def generate_response(system_prompt, user_prompt):
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
    return response["message"]["content"]
