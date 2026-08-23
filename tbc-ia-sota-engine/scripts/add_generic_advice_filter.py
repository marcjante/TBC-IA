#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade un filtro determinista (no depende del LLM) que descarta las
"afirmaciones no respaldadas" que en realidad son puro consejo generico
de acompañamiento ("mantén un registro de tus síntomas", "sigue las
instrucciones de tu médico", "mantén una buena higiene"...) — detectado
en pruebas reales el 23 de agosto de 2026, tras añadir la ampliacion de
consultas: el verificador empezo a marcar este tipo de frases aunque su
propia instruccion ya le decia que no lo hiciera.

Mismo principio que el filtro de cordura (claim_actually_in_response):
un segundo filtro independiente del LLM, para que la inconsistencia del
modelo en seguir sus propias instrucciones no cuele falsos positivos.

Uso:
    python3 add_generic_advice_filter.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    claims = parse_verification_response(raw)
    if claims is None:
        print(f"[DEBUG verify_claims_with_llm] No se pudo parsear la respuesta del verificador. Raw: {raw!r}")
        return None
    return [c for c in claims if claim_actually_in_response(c, response_text)]'''

NEW = '''    claims = parse_verification_response(raw)
    if claims is None:
        print(f"[DEBUG verify_claims_with_llm] No se pudo parsear la respuesta del verificador. Raw: {raw!r}")
        return None
    return [
        c for c in claims
        if claim_actually_in_response(c, response_text) and not is_generic_advice(c)
    ]


GENERIC_ADVICE_PATTERNS = [
    "mantén un registro de tus síntomas",
    "mantén una buena higiene",
    "sigue las instrucciones de tu médico",
    "sigue las instrucciones de tu equipo",
    "habla con tu equipo de tratamiento",
    "consulta a tu médico",
    "consulta con tu médico",
    "busca atención médica",
    "contacta con tu médico",
    "comunícate con tu médico",
]


def is_generic_advice(claim):
    """Descarta frases que son puro consejo generico de acompañamiento
    (ej. "mantén una buena higiene"), aunque el verificador LLM las haya
    marcado como "no respaldadas" — su propia instruccion ya le pide no
    marcarlas, pero no siempre lo cumple de forma consistente. Solo
    descarta si la frase es CASI ENTERAMENTE el consejo generico (queda
    muy poco texto tras quitarlo); si la frase mezcla el consejo con
    contenido clinico especifico adicional, no se descarta."""
    import re
    normalized = re.sub(r"[^\\w\\s]", "", claim.strip().lower())
    for pattern in GENERIC_ADVICE_PATTERNS:
        pattern_norm = re.sub(r"[^\\w\\s]", "", pattern)
        if pattern_norm in normalized:
            remainder = normalized.replace(pattern_norm, "", 1).strip()
            if len(remainder) < 20:
                return True
    return False'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_generic_advice_filter.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "is_generic_advice" in content:
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
