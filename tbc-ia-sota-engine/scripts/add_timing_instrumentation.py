#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade cronometraje a cada paso de /api/chat, para saber con datos reales
(no suposiciones) donde se van los minutos de una respuesta lenta:
clasificador de intencion, ampliacion de consulta, retrieval hibrido,
generacion principal, verificacion, y consenso con Mistral.

Es una instrumentacion de diagnostico (imprime en el log), no cambia
ningun comportamiento. Se puede quitar despues de tener los datos, o
convertirla en algo permanente si resulta util.

Uso:
    python3 add_timing_instrumentation.py "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# 1. classify_intent()
# ---------------------------------------------------------------

OLD_1 = '''    try:
        raw = generate_response(INTENT_CLASSIFIER_SYSTEM_PROMPT, message)
        parsed = parse_comparator_response(raw)
        if parsed and parsed.get("intencion") in ("urgencia_medica", "riesgo_autolesion"):
            return parsed["intencion"]
    except Exception:
        pass
    return "consulta_clinica"'''

NEW_1 = '''    import time
    _t0 = time.time()
    try:
        raw = generate_response(INTENT_CLASSIFIER_SYSTEM_PROMPT, message)
        print(f"[TIMING] classify_intent: {time.time() - _t0:.1f}s")
        parsed = parse_comparator_response(raw)
        if parsed and parsed.get("intencion") in ("urgencia_medica", "riesgo_autolesion"):
            return parsed["intencion"]
    except Exception:
        pass
    return "consulta_clinica"'''

# ---------------------------------------------------------------
# 2. expand_query()
# ---------------------------------------------------------------

OLD_2 = '''    try:
        raw = generate_response(QUERY_EXPANSION_SYSTEM_PROMPT, original_query)
        terminos = raw.strip()
        if not terminos or len(terminos) > 300:
            return original_query
        return f"{original_query} {terminos}"
    except Exception:
        return original_query'''

NEW_2 = '''    import time
    _t0 = time.time()
    try:
        raw = generate_response(QUERY_EXPANSION_SYSTEM_PROMPT, original_query)
        print(f"[TIMING] expand_query: {time.time() - _t0:.1f}s")
        terminos = raw.strip()
        if not terminos or len(terminos) > 300:
            return original_query
        return f"{original_query} {terminos}"
    except Exception:
        return original_query'''

# ---------------------------------------------------------------
# 3. hybrid_retrieve() en /api/chat
# ---------------------------------------------------------------

OLD_3 = '''    retrieval_query = build_retrieval_query(request.message, request.history)
    retrieval_query = expand_query(retrieval_query)
    fragments, metadatas, distances = hybrid_retrieve(retrieval_query, request.top_k)'''

NEW_3 = '''    retrieval_query = build_retrieval_query(request.message, request.history)
    retrieval_query = expand_query(retrieval_query)
    import time
    _t_retrieve = time.time()
    fragments, metadatas, distances = hybrid_retrieve(retrieval_query, request.top_k)
    print(f"[TIMING] hybrid_retrieve: {time.time() - _t_retrieve:.1f}s")'''

# ---------------------------------------------------------------
# 4. generate_response() principal
# ---------------------------------------------------------------

OLD_4 = '''    final_response = generate_response(SYSTEM_PROMPT, user_prompt)'''

NEW_4 = '''    import time
    _t_gen = time.time()
    final_response = generate_response(SYSTEM_PROMPT, user_prompt)
    print(f"[TIMING] generate_response (respuesta principal): {time.time() - _t_gen:.1f}s")'''

# ---------------------------------------------------------------
# 5. verify_claims_with_llm()
# ---------------------------------------------------------------

OLD_5 = '''    llm_unsupported_claims = None
    if sources_used:
        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims'''

NEW_5 = '''    llm_unsupported_claims = None
    if sources_used:
        import time
        _t_verify = time.time()
        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        print(f"[TIMING] verify_claims_with_llm: {time.time() - _t_verify:.1f}s")
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims'''

# ---------------------------------------------------------------
# 6. Mistral (query_llamafile_response + compare_with_llamafile)
# ---------------------------------------------------------------

OLD_6 = '''    riesgo_o_duda = bool(llm_unsupported_claims) or result.get("coverage") in ("baja", "complementaria")
    if riesgo_o_duda and sources_used:
        response_b = query_llamafile_response(context_text, request.message)
        if response_b is not None:
            dual_model_comparison = compare_with_llamafile(final_response, response_b)
            if dual_model_comparison is not None:
                result.setdefault("debug_info", {})["dual_model_comparison"] = {
                    "response_b": response_b,
                    **dual_model_comparison,
                }'''

NEW_6 = '''    riesgo_o_duda = bool(llm_unsupported_claims) or result.get("coverage") in ("baja", "complementaria")
    if riesgo_o_duda and sources_used:
        import time
        _t_mistral = time.time()
        response_b = query_llamafile_response(context_text, request.message)
        print(f"[TIMING] query_llamafile_response: {time.time() - _t_mistral:.1f}s")
        if response_b is not None:
            _t_compare = time.time()
            dual_model_comparison = compare_with_llamafile(final_response, response_b)
            print(f"[TIMING] compare_with_llamafile: {time.time() - _t_compare:.1f}s")
            if dual_model_comparison is not None:
                result.setdefault("debug_info", {})["dual_model_comparison"] = {
                    "response_b": response_b,
                    **dual_model_comparison,
                }'''


PATCHES = [
    (OLD_1, NEW_1, "classify_intent"),
    (OLD_2, NEW_2, "expand_query"),
    (OLD_3, NEW_3, "hybrid_retrieve (llamada en /api/chat)"),
    (OLD_4, NEW_4, "generate_response (respuesta principal)"),
    (OLD_5, NEW_5, "verify_claims_with_llm"),
    (OLD_6, NEW_6, "Mistral (query_llamafile_response + compare_with_llamafile)"),
]


def apply_patch(path, old, new, label):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if new in content:
        print(f"  {label}: ya estaba aplicado (no se ha tocado nada).")
        return content, False

    count = content.count(old)
    if count == 0:
        print(f"  {label}: ABORTADO, no se encontró el bloque esperado. No se ha escrito nada de este paso.")
        return content, False
    if count > 1:
        print(f"  {label}: ABORTADO, el bloque aparece {count} veces (debería ser único). No se ha escrito nada de este paso.")
        return content, False

    content = content.replace(old, new, 1)
    print(f"  {label}: aplicado correctamente.")
    return content, True


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_timing_instrumentation.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    any_applied = False
    for old, new, label in PATCHES:
        content, applied = apply_patch(path, old, new, label)
        any_applied = any_applied or applied
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    print("\nHecho. Reinicia TBC-AI y mira ~/tbc_stack_logs/tbc_ai.log tras la siguiente pregunta.")


if __name__ == "__main__":
    main()
