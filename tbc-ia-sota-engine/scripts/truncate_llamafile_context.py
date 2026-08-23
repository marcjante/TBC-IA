#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recorta el contexto que se manda a Llamafile/Mistral, igual que ya se
hace para el verificador (verify_claims_with_llm). Hallazgo del 23 de
agosto de 2026: tras añadir hybrid_retrieve() (mas fuentes recuperadas
por pregunta), Llamafile empezo a fallar consistentemente por timeout
(90s) en preguntas con contexto grande — no estaba colgado, simplemente
tardaba mas de 90s en procesar un contexto tan grande en este hardware.

Solo afecta a lo que ve Llamafile (la señal secundaria de consenso); el
contexto completo se sigue usando sin recortar para la respuesta
principal de Llama 3.1.

Uso:
    python3 truncate_llamafile_context.py "/ruta/a/backend/rag.py"
"""

import sys

OLD = '''    system_prompt = (
        "Eres un asistente clinico. Responde la pregunta del paciente "
        "usando exclusivamente el CONTEXTO proporcionado. No inventes "
        "informacion que no este en el contexto."
    )
    user_prompt = f"CONTEXTO:\\n{context_text}\\n\\nPREGUNTA:\\n{question}"'''

NEW = '''    # Recorte del contexto para Llamafile especificamente (no afecta al
    # contexto completo usado por Llama 3.1 para la respuesta principal).
    # Hallazgo del 23 de agosto de 2026: tras hybrid_retrieve() (mas
    # fuentes por pregunta), Llamafile empezo a fallar por timeout de
    # forma consistente con contextos grandes — no estaba colgado,
    # simplemente tardaba mas de 90s en procesarlos en este hardware.
    MAX_LLAMAFILE_CONTEXT_CHARS = 6000
    if len(context_text) > MAX_LLAMAFILE_CONTEXT_CHARS:
        context_text = context_text[:MAX_LLAMAFILE_CONTEXT_CHARS] + "\\n\\n[...contexto recortado para el segundo modelo...]"

    system_prompt = (
        "Eres un asistente clinico. Responde la pregunta del paciente "
        "usando exclusivamente el CONTEXTO proporcionado. No inventes "
        "informacion que no este en el contexto."
    )
    user_prompt = f"CONTEXTO:\\n{context_text}\\n\\nPREGUNTA:\\n{question}"'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 truncate_llamafile_context.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "MAX_LLAMAFILE_CONTEXT_CHARS" in content:
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
