#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pieza 4 de 8: porta al chat de pacientes el mismo hallazgo e igual
correccion que en /api/chat: la verificacion de afirmaciones y Mistral
estaban atados por completo a request.debug=True, lo que significa que
las consultas reales de pacientes nunca se beneficiaban de estas
comprobaciones de seguridad.

Cambios:
  1. El calculo de "cobertura interna" se mueve ANTES de la
     verificacion (antes se calculaba al final, solo para el registro),
     para poder usarlo como señal de riesgo.
  2. La verificacion de afirmaciones se ejecuta SIEMPRE que haya
     fuentes, sin depender de debug.
  3. Mistral se activa de forma SELECTIVA: solo si hay afirmaciones sin
     respaldo, o si la cobertura interna es baja/complementaria — no en
     cada pregunta.
  4. Los resultados se guardan en debug_info tanto si debug es True como
     si no, igual que en /api/chat.

Uso:
    python3 add_patient_always_on_verification.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    result = {"response": final_response}
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": 8,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fallback_used": fallback_used,
        }

        if fragments:
            llm_unsupported_claims = verify_claims_with_llm(fragments, final_response)
            if llm_unsupported_claims is not None:
                result["debug_info"]["llm_unsupported_claims"] = llm_unsupported_claims

            response_b = query_llamafile_response(context_text, request.message)
            if response_b is not None:
                dual_model_comparison = compare_with_llamafile(final_response, response_b)
                if dual_model_comparison is not None:
                    result["debug_info"]["dual_model_comparison"] = {
                        "response_b": response_b,
                        **dual_model_comparison,
                    }

    # Cobertura interna, solo para el registro de patrones de uso (no se
    # muestra al paciente, igual que las fuentes: aqui usamos los mismos
    # umbrales que en /api/chat para mantener las estadisticas comparables
    # entre ambos endpoints).
    if fallback_used:
        internal_coverage = "complementaria"
    elif distances:
        best_distance = distances[0]
        if best_distance <= 400:
            internal_coverage = "alta"
        elif best_distance <= 600:
            internal_coverage = "media"
        else:
            internal_coverage = "baja"
    else:
        internal_coverage = None
    log_usage_pattern("/api/patient-chat", internal_coverage, lang=request.lang)

    return result'''

NEW = '''    # Cobertura interna (se calcula AHORA, antes de la verificacion, para
    # poder usarla como señal de riesgo — igual que "coverage" en
    # /api/chat). Sigue sin mostrarse al paciente, solo para el registro
    # de patrones de uso y para decidir si activar Mistral.
    if fallback_used:
        internal_coverage = "complementaria"
    elif distances:
        best_distance = distances[0]
        if best_distance <= 400:
            internal_coverage = "alta"
        elif best_distance <= 600:
            internal_coverage = "media"
        else:
            internal_coverage = "baja"
    else:
        internal_coverage = None

    result = {"response": final_response}
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": 8,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fallback_used": fallback_used,
        }

    # Verificacion de afirmaciones: SIEMPRE se ejecuta si hay fuentes, no
    # solo en modo debug (mismo hallazgo que en /api/chat: antes las
    # consultas reales de pacientes nunca se beneficiaban de esta
    # comprobacion de seguridad).
    llm_unsupported_claims = None
    if fragments:
        llm_unsupported_claims = verify_claims_with_llm(fragments, final_response)
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims

    # Mistral (critico selectivo): solo si hay señal de riesgo real
    # (afirmaciones sin respaldo, o cobertura baja/complementaria) — no
    # en cada pregunta. Mismo criterio que /api/chat.
    riesgo_o_duda = bool(llm_unsupported_claims) or internal_coverage in ("baja", "complementaria")
    if riesgo_o_duda and fragments:
        response_b = query_llamafile_response(context_text, request.message)
        if response_b is not None:
            dual_model_comparison = compare_with_llamafile(final_response, response_b)
            if dual_model_comparison is not None:
                result.setdefault("debug_info", {})["dual_model_comparison"] = {
                    "response_b": response_b,
                    **dual_model_comparison,
                }

    log_usage_pattern("/api/patient-chat", internal_coverage, lang=request.lang)

    return result'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_patient_always_on_verification.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "Cobertura interna (se calcula AHORA" in content:
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
