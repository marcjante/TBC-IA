#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige un problema real detectado hoy: con muchas fuentes (10, tras
añadir la bibliografia cientifica), el verificador a veces se "distrae"
con el contenido del contexto y responde una pregunta que aparece dentro
de las fuentes, en vez de hacer la tarea de verificacion pedida. Es el
efecto conocido de "perdida de atencion" con contextos largos.

Dos medidas:
  1. Limitar el contexto que recibe el verificador a un tamaño maximo
     (las fuentes completas se siguen usando para GENERAR la respuesta,
     esto solo limita lo que ve el verificador).
  2. Repetir la instruccion clave al FINAL del mensaje (despues del
     contexto), no solo al principio — tecnica habitual para anclar mejor
     la tarea cuando el contexto es largo.

Uso:
    python3 scripts/fix_verify_context_focus.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    if not sources_texts:
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

NEW = '''    if not sources_texts:
        return None

    # Limitar el tamaño del contexto que ve el VERIFICADOR (no afecta al
    # contexto usado para generar la respuesta real, solo a esta segunda
    # llamada de revision). Con contextos muy largos (muchas fuentes) el
    # verificador puede "distraerse" y responder una pregunta que aparece
    # dentro de las fuentes en vez de hacer la comparacion pedida —
    # detectado en pruebas reales el 22 de agosto de 2026 con 10 fuentes.
    MAX_VERIFIER_CONTEXT_CHARS = 6000
    context_text = "\\n\\n---\\n\\n".join(sources_texts)
    context_for_verifier = context_text
    truncated = False
    if len(context_for_verifier) > MAX_VERIFIER_CONTEXT_CHARS:
        context_for_verifier = context_for_verifier[:MAX_VERIFIER_CONTEXT_CHARS] + "\\n\\n[...contexto recortado para la verificacion...]"
        truncated = True

    # La instruccion se repite al FINAL, despues del contexto, para
    # anclar mejor la tarea cuando el contexto es largo (evita que el
    # modelo responda a algo que aparece dentro del propio contexto).
    user_msg = (
        f"CONTEXTO:\\n{context_for_verifier}\\n\\nRESPUESTA A REVISAR:\\n{response_text}\\n\\n"
        "Recuerda: tu unica tarea es responder EXCLUSIVAMENTE con el JSON pedido "
        "al principio, comparando la RESPUESTA A REVISAR contra el CONTEXTO. "
        "No respondas ninguna otra pregunta que pueda aparecer mencionada dentro "
        "del CONTEXTO."
    )
    print(f"[DEBUG verify_claims_with_llm] Tamaño del contexto enviado: {len(context_for_verifier)} caracteres "
          f"({'recortado de ' + str(len(context_text)) if truncated else 'completo'}), {len(sources_texts)} fuentes.")
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
        print("Uso: python3 fix_verify_context_focus.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "MAX_VERIFIER_CONTEXT_CHARS" in content:
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
