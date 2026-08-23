#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hace visible en el log el error real cuando compare_with_llamafile() falla
(hasta ahora se descartaba en silencio, por diseno fail-open). No cambia
el comportamiento: sigue devolviendo None si falla, solo añade un print()
con el detalle del fallo para poder diagnosticarlo.

Uso:
    python3 scripts/debug_compare_with_llamafile.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    user_prompt = f"RESPUESTA A:\\n{response_a}\\n\\nRESPUESTA B:\\n{response_b}"
    try:
        raw = generate_response(COMPARATOR_SYSTEM_PROMPT, user_prompt)
    except Exception:
        return None
    return parse_comparator_response(raw)'''

NEW = '''    user_prompt = f"RESPUESTA A:\\n{response_a}\\n\\nRESPUESTA B:\\n{response_b}"
    try:
        raw = generate_response(COMPARATOR_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        print(f"[DEBUG compare_with_llamafile] Fallo en generate_response: {type(e).__name__}: {e}")
        return None
    parsed = parse_comparator_response(raw)
    if parsed is None:
        print(f"[DEBUG compare_with_llamafile] No se pudo parsear la respuesta del comparador. Raw: {raw!r}")
    return parsed'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 debug_compare_with_llamafile.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "[DEBUG compare_with_llamafile]" in content:
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
