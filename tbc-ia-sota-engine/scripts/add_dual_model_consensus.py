#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integra el consenso entre dos modelos (Ollama + Llamafile/Mistral) en
/api/chat, como señal secundaria en debug_info. Requiere que rag.py ya
tenga query_llamafile_response() (ver add_dual_model_consensus_rag.py o
la copia manual de rag.py con esa función añadida al final).

No altera la respuesta real al paciente: solo añade informacion a
debug_info cuando request.debug=True, igual que llm_unsupported_claims.

Uso:
    python3 scripts/add_dual_model_consensus.py "/ruta/a/backend/main.py"
"""

import sys

# --- 1. Import: extender con query_llamafile_response ---
FINAL_IMPORT = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response"
IMPORT_VARIANTS = [
    "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness",
]

# --- 2. Insertar funciones del comparador, justo despues de verify_claims_with_llm ---
ANCHOR_AFTER_VERIFY = '''    claims = parse_verification_response(raw)
    if claims is None:
        return None
    return [c for c in claims if claim_actually_in_response(c, response_text)]'''

COMPARATOR_BLOCK = '''    claims = parse_verification_response(raw)
    if claims is None:
        return None
    return [c for c in claims if claim_actually_in_response(c, response_text)]


# ==============================================================================
# CONSENSO ENTRE DOS MODELOS (Ollama + Llamafile/Mistral) - agosto 2026
# ==============================================================================
# Señal secundaria (complementaria a verify_claims_with_llm, que es la
# principal): genera una respuesta independiente con un segundo modelo
# para la misma pregunta y contexto, y compara si coinciden en sus
# afirmaciones. Probado hoy como prototipo en dual_model_check.py: util
# para detectar cuando un modelo añade algo que el otro no dice, pero NO
# sustituye a la verificacion contra fuentes (si los dos modelos comparten
# el mismo sesgo de entrenamiento, pueden fabricar la misma idea sin que
# esto lo note - ver seccion 8.3 del resumen del sistema).

COMPARATOR_SYSTEM_PROMPT = """Se te dan dos respuestas (A y B) generadas por dos modelos distintos a la misma pregunta clinica sobre tuberculosis, a partir del mismo contexto documental.

Identifica afirmaciones clinicas o factuales CONCRETAS que aparecen en una respuesta pero no en la otra (sintomas, causas, tratamientos, pronosticos). No cuentes frases genericas de acompanamiento ("habla con tu equipo medico") ni reformulaciones equivalentes con otras palabras.

Responde EXCLUSIVAMENTE con un JSON con este formato exacto, sin texto antes ni despues:
{"claims_only_in_a": ["..."], "claims_only_in_b": ["..."], "agreement": "alto"|"medio"|"bajo"}

"agreement" = "alto" si no hay afirmaciones discrepantes relevantes; "medio" si hay alguna discrepancia menor; "bajo" si hay afirmaciones claramente contradictorias o solo una de las dos respuestas las menciona."""


def parse_comparator_response(raw):
    """Extrae el JSON del comparador, tolerando bloques de codigo o texto
    alrededor (mismo patron que parse_verification_response)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        pass
    match = re.search(r"\\{.*\\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, AttributeError):
            return None
    return None


def compare_with_llamafile(response_a, response_b):
    """Usa Ollama (via generate_response, ya validado hoy como buen juez)
    para comparar dos respuestas de modelos distintos a la misma pregunta.
    Devuelve None si falla cualquier paso (fail-open)."""
    user_prompt = f"RESPUESTA A:\\n{response_a}\\n\\nRESPUESTA B:\\n{response_b}"
    try:
        raw = generate_response(COMPARATOR_SYSTEM_PROMPT, user_prompt)
    except Exception:
        return None
    return parse_comparator_response(raw)'''

# --- 3. Wire en el bloque debug de /api/chat: añadir tras llm_unsupported_claims ---
ANCHOR_CHAT_DEBUG = '''        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)'''

CHAT_DEBUG_BLOCK = '''        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims

        response_b = query_llamafile_response(context_text, request.message)
        if response_b is not None:
            dual_model_comparison = compare_with_llamafile(final_response, response_b)
            if dual_model_comparison is not None:
                result.setdefault("debug_info", {})["dual_model_comparison"] = {
                    "response_b": response_b,
                    **dual_model_comparison,
                }

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)'''


def apply_import_patch(content):
    if FINAL_IMPORT in content:
        return content, False, None
    for variant in IMPORT_VARIANTS:
        count = content.count(variant)
        if count == 1:
            return content.replace(variant, FINAL_IMPORT, 1), True, None
        if count > 1:
            return content, False, f"el import aparece {count} veces, debería ser único"
    return content, False, "no se encontró ninguna variante conocida del import de backend.rag"


def apply_comparator_functions_patch(content):
    if "def compare_with_llamafile" in content:
        return content, False, None
    count = content.count(ANCHOR_AFTER_VERIFY)
    if count == 0:
        return content, False, "no se encontró el final de verify_claims_with_llm (¿archivo distinto al esperado?)"
    if count > 1:
        return content, False, f"el ancla aparece {count} veces, debería ser única"
    return content.replace(ANCHOR_AFTER_VERIFY, COMPARATOR_BLOCK, 1), True, None


def apply_chat_debug_patch(content):
    if "dual_model_comparison" in content:
        return content, False, None
    count = content.count(ANCHOR_CHAT_DEBUG)
    if count == 0:
        return content, False, "no se encontró el bloque debug de /api/chat esperado"
    if count > 1:
        return content, False, f"el ancla aparece {count} veces, debería ser única"
    return content.replace(ANCHOR_CHAT_DEBUG, CHAT_DEBUG_BLOCK, 1), True, None


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_dual_model_consensus.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    applied = []
    skipped = []
    errors = []

    content, ok, err = apply_import_patch(content)
    if err:
        errors.append(f"Import: {err}")
    elif ok:
        applied.append("import")
    else:
        skipped.append("import")

    content, ok, err = apply_comparator_functions_patch(content)
    if err:
        errors.append(f"Funciones del comparador: {err}")
    elif ok:
        applied.append("comparator_functions")
    else:
        skipped.append("comparator_functions")

    content, ok, err = apply_chat_debug_patch(content)
    if err:
        errors.append(f"Bloque debug /api/chat: {err}")
    elif ok:
        applied.append("chat_debug_wiring")
    else:
        skipped.append("chat_debug_wiring")

    if errors:
        print("ABORTADO. No se ha escrito nada en el archivo. Problemas encontrados:")
        for e in errors:
            print(" -", e)
        sys.exit(1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Cambios aplicados: {applied}")
    if skipped:
        print(f"Cambios ya presentes (no tocados): {skipped}")
    print(f"Archivo actualizado: {path}")


if __name__ == "__main__":
    main()
