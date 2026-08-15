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
    return response["message"]["content"]
