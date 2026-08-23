#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige un hallazgo importante encontrado el 23 de agosto de 2026: la
verificacion de afirmaciones (verify_claims_with_llm) y la comparacion
con Mistral (query_llamafile_response + compare_with_llamafile) estaban
atadas por completo a request.debug=True. Esto significa que en el uso
real (pacientes/profesionales sin mandar debug:true), NINGUNA de las dos
comprobaciones de seguridad se ejecutaba nunca.

Cambios:
  1. La verificacion de afirmaciones se ejecuta SIEMPRE que haya fuentes
     (sources_used no vacio), sin depender de debug. Es una medida de
     seguridad, no una ayuda de depuracion.
  2. Mistral (el critico/segundo modelo) se ejecuta de forma SELECTIVA:
     solo cuando hay señal de riesgo real (se encontraron afirmaciones
     sin respaldo, o la cobertura es "baja"/"complementaria") — no en
     cada pregunta, ahorrando latencia en el caso comun. Esto tambien
     ocurre independientemente de debug (Fase 6 de la propuesta de
     arquitectura TBC-AI v2, agosto 2026).
  3. Los resultados de ambas comprobaciones se guardan en debug_info
     tanto si request.debug es True como si no (para que el llamador
     real, no solo el modo de prueba, vea la señal de seguridad).

Uso:
    python3 decouple_verification_from_debug.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": request.top_k,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fragments_retrieved": len(fragments),
            "fallback_used": fallback_used,
        }

    if request.debug and sources_used:
        llm_unsupported_claims = verify_claims_with_llm(
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

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)

    return result'''

NEW = '''    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": request.top_k,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fragments_retrieved": len(fragments),
            "fallback_used": fallback_used,
        }

    # Verificacion de afirmaciones: SIEMPRE se ejecuta si hay fuentes, no
    # solo en modo debug. Antes solo corria con debug=true, lo que
    # significaba que las consultas reales (sin ese parametro) nunca se
    # beneficiaban de esta comprobacion de seguridad — hallazgo del 23 de
    # agosto de 2026, corregido aqui.
    llm_unsupported_claims = None
    if sources_used:
        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims

    # Mistral (critico selectivo): solo se ejecuta si hay señal de riesgo
    # o duda real (afirmaciones sin respaldo detectadas, o cobertura
    # baja/complementaria) — no en cada pregunta. Antes se ejecutaba solo
    # en modo debug, sin ningun criterio de riesgo (Fase 6 de la
    # propuesta de arquitectura TBC-AI v2, agosto 2026).
    riesgo_o_duda = bool(llm_unsupported_claims) or result.get("coverage") in ("baja", "complementaria")
    if riesgo_o_duda and sources_used:
        response_b = query_llamafile_response(context_text, request.message)
        if response_b is not None:
            dual_model_comparison = compare_with_llamafile(final_response, response_b)
            if dual_model_comparison is not None:
                result.setdefault("debug_info", {})["dual_model_comparison"] = {
                    "response_b": response_b,
                    **dual_model_comparison,
                }

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)

    return result'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 decouple_verification_from_debug.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "riesgo_o_duda" in content:
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
