#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cierra el hueco de "control de alucinaciones" señalado hoy: hasta ahora,
cuando se detectaba riesgo (afirmaciones sin respaldo o cobertura baja),
esa señal solo se guardaba en debug_info — la respuesta real que veia
el usuario no cambiaba en nada.

Decision tomada conscientemente en vez de bloquear la respuesta entera
o regenerarla (lo que costaria una llamada extra a Ollama, ya vamos
justos de tiempo): se añade un AVISO CLARO al final de la respuesta
real cuando riesgo_o_duda es verdadero. No oculta informacion
potencialmente util, no cuesta tiempo extra, y es honesto sobre la
incertidumbre.

Uso:
    python3 add_risk_disclaimer_chat.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    riesgo_o_duda = bool(llm_unsupported_claims) or result.get("coverage") in ("baja", "complementaria")
    if riesgo_o_duda and sources_used:
        import time
        _t_mistral = time.time()
        response_b = query_llamafile_response(context_text, request.message)'''

NEW = '''    riesgo_o_duda = bool(llm_unsupported_claims) or result.get("coverage") in ("baja", "complementaria")

    # Aviso explicito en la respuesta real cuando hay riesgo o duda (no
    # solo en debug_info, que antes de hoy era lo unico que cambiaba).
    # No se bloquea ni se regenera la respuesta (costaria una llamada
    # extra a Ollama); se añade un aviso honesto sobre la incertidumbre.
    if riesgo_o_duda:
        result["response"] = result["response"] + (
            "\\n\\nNota: parte de esta información no se ha podido verificar "
            "directamente contra las fuentes documentales. Coméntalo con tu "
            "equipo médico antes de actuar según esto."
        )

    if riesgo_o_duda and sources_used:
        import time
        _t_mistral = time.time()
        response_b = query_llamafile_response(context_text, request.message)'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_risk_disclaimer_chat.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "Aviso explicito en la respuesta real" in content:
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
