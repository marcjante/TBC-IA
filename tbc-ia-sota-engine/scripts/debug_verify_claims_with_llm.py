#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hace visible en el log el error real cuando verify_claims_with_llm() falla
(hasta ahora se descartaba en silencio, por diseno fail-open). No cambia
el comportamiento: sigue devolviendo None si falla, solo añade un print()
con el detalle del fallo para poder diagnosticarlo — mismo patron que ya
se aplico hoy a compare_with_llamafile.

Uso:
    python3 scripts/debug_verify_claims_with_llm.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    if not sources_texts:
        return None
    context_text = "\\n\\n---\\n\\n".join(sources_texts)
    user_msg = f"CONTEXTO:\\n{context_text}\\n\\nRESPUESTA A REVISAR:\\n{response_text}"
    try:
        raw = generate_response(VERIFICATION_SYSTEM_PROMPT, user_msg)
    except Exception:
        return None
    claims = parse_verification_response(raw)
    if claims is None:
        return None
    return [c for c in claims if claim_actually_in_response(c, response_text)]'''

NEW = '''    if not sources_texts:
        return None
    context_text = "\\n\\n---\\n\\n".join(sources_texts)
    user_msg = f"CONTEXTO:\\n{context_text}\\n\\nRESPUESTA A REVISAR:\\n{response_text}"
    print(f"[DEBUG verify_claims_with_llm] Tamaño del contexto enviado: {len(context_text)} caracteres, "
          f"{len(sources_texts)} fuentes.")
    try:
        raw = generate_response(VERIFICATION_SYSTEM_PROMPT, user_msg)
    except Exception as e:
        print(f"[DEBUG verify_claims_with_llm] Fallo en generate_response: {type(e).__name__}: {e}")
        return None
    claims = parse_verification_response(raw)
    if claims is None:
        print(f"[DEBUG verify_claims_with_llm] No se pudo parsear la respuesta del verificador. Raw: {raw!r}")
        return None
    return [c for c in claims if claim_actually_in_response(c, response_text)]'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 debug_verify_claims_with_llm.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "[DEBUG verify_claims_with_llm]" in content:
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
