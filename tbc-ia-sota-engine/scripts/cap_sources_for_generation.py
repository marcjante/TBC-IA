#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Limita el numero de fuentes que ve el GENERADOR PRINCIPAL (Llama 3.1),
manteniendo intacta la lista completa de "sources_used" que se devuelve
al usuario para citar. Hallazgo con cronometraje real el 23 de agosto de
2026: generate_response() para la respuesta principal tardaba 131.5s con
10 fuentes en el contexto — con diferencia el paso mas caro de todo
/api/chat (de un total de ~259s).

Las fuentes ya vienen ordenadas por relevancia (fusion RRF de
hybrid_retrieve + las 2 de bibliografia añadidas al final), asi que
recortar la "cola" para el generador pierde poca informacion util a
cambio de una reduccion real y medible de tiempo. La lista de fuentes
citadas al usuario NO se recorta, solo lo que efectivamente procesa el
modelo para redactar la respuesta.

Uso:
    python3 cap_sources_for_generation.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    context_text = "\\n\\n---\\n\\n".join(context_parts)
    history_block = build_history_block(request.history)'''

NEW = '''    # Limitar el numero de fuentes que ve el GENERADOR principal (no afecta
    # a sources_used, que sigue completo para citar al usuario). Hallazgo
    # del 23 de agosto de 2026 con cronometraje real: generate_response()
    # tardaba 131.5s con 10 fuentes en el contexto — con diferencia el paso
    # mas caro de /api/chat. Las fuentes ya vienen ordenadas por relevancia
    # (RRF de hybrid_retrieve + bibliografia), asi que recortar la "cola"
    # pierde poca informacion util a cambio de una reduccion real de tiempo.
    MAX_SOURCES_FOR_GENERATION = 5
    context_text = "\\n\\n---\\n\\n".join(context_parts[:MAX_SOURCES_FOR_GENERATION])
    history_block = build_history_block(request.history)'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 cap_sources_for_generation.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "MAX_SOURCES_FOR_GENERATION" in content:
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
