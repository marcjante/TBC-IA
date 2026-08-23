#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade un filtro de cordura a verify_claims_with_llm() en backend/main.py:
descarta afirmaciones marcadas por el verificador que ni siquiera aparecen
(por solapamiento de palabras) en el texto real de la respuesta revisada.

Detectado hoy en pruebas: el propio LLM verificador puede "alucinar" una
frase inexistente al revisar, marcandola como no respaldada, aunque nunca
estuvo en la respuesta original. Sin este filtro, esas alucinaciones del
verificador se mostrarian igual que detecciones reales.

Uso:
    python3 scripts/add_claim_sanity_filter.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''def verify_claims_with_llm(sources_texts, response_text):
    """Pide al propio LLM (via generate_response, ya usado en el resto de
    TBC-AI) que revise la respuesta ya generada contra las fuentes, en una
    llamada aparte. NO decide nada sobre la respuesta: solo informa.
    Devuelve None si falla cualquier paso (fail-open, no bloquea el flujo
    normal por un fallo de esta verificacion adicional)."""
    if not sources_texts:
        return None
    context_text = "\\n\\n---\\n\\n".join(sources_texts)
    user_msg = f"CONTEXTO:\\n{context_text}\\n\\nRESPUESTA A REVISAR:\\n{response_text}"
    try:
        raw = generate_response(VERIFICATION_SYSTEM_PROMPT, user_msg)
    except Exception:
        return None
    return parse_verification_response(raw)'''

NEW = '''def normalize_text_for_claim_check(text):
    text = text.lower()
    for a, b in [("\\u00e1", "a"), ("\\u00e9", "e"), ("\\u00ed", "i"), ("\\u00f3", "o"), ("\\u00fa", "u"), ("\\u00f1", "n")]:
        text = text.replace(a, b)
    text = re.sub(r"[^\\w\\s]", " ", text)
    return text


def claim_actually_in_response(claim, response_text, threshold=0.5):
    """Comprueba que una afirmacion marcada por el verificador realmente
    aparece (por solapamiento de palabras) en el texto de la respuesta
    revisada. Descubierto en pruebas (agosto 2026): el propio LLM
    verificador puede marcar una frase que ni siquiera esta en el texto
    original — una alucinacion del verificador, no una deteccion real."""
    claim_words = set(normalize_text_for_claim_check(claim).split())
    if not claim_words:
        return False
    response_words = set(normalize_text_for_claim_check(response_text).split())
    overlap = len(claim_words & response_words) / len(claim_words)
    return overlap >= threshold


def verify_claims_with_llm(sources_texts, response_text):
    """Pide al propio LLM (via generate_response, ya usado en el resto de
    TBC-AI) que revise la respuesta ya generada contra las fuentes, en una
    llamada aparte. NO decide nada sobre la respuesta: solo informa.
    Devuelve None si falla cualquier paso (fail-open, no bloquea el flujo
    normal por un fallo de esta verificacion adicional).

    Filtra ademas las afirmaciones marcadas que no aparecen realmente en
    response_text (alucinaciones del propio verificador, ver
    claim_actually_in_response)."""
    if not sources_texts:
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


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_claim_sanity_filter.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "claim_actually_in_response" in content:
        print("Ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(OLD)
    if count == 0:
        print("ABORTADO: no se encontró el bloque esperado (verify_claims_with_llm). "
              "No se ha escrito nada. Revisa a mano.")
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
