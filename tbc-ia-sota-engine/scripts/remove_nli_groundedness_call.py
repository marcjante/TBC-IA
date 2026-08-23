#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quita la llamada a verify_groundedness() en /api/chat, dejando solo
verify_claims_with_llm() (el chequeo NLI resultó no ser útil en pruebas
reales: marcaba casi todo como no respaldado, sin distinguir casos).

No borra la funcion verify_groundedness() de rag.py ni el motor
complementario (por si se quiere retomar mas adelante con otro modelo NLI),
solo deja de llamarla desde aqui para no gastar tiempo de computo en algo
que no aporta.

Uso:
    python3 scripts/remove_nli_groundedness_call.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    if request.debug and sources_used:
        groundedness = verify_groundedness(
            final_response,
            [s["text"] for s in sources_used],
        )
        if groundedness is not None:
            result.setdefault("debug_info", {})["groundedness"] = groundedness

        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)

    return result


@app.post("/api/upload")'''

NEW = '''    if request.debug and sources_used:
        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)

    return result


@app.post("/api/upload")'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 remove_nli_groundedness_call.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if NEW in content:
        print("Ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(OLD)
    if count == 0:
        print("ABORTADO: no se encontró el bloque esperado. No se ha escrito nada.")
        print("Puede que el archivo tenga un estado distinto al esperado — revisa a mano.")
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
