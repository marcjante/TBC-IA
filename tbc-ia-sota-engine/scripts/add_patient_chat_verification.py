#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extiende la verificación de afirmaciones fabricadas (fuentes + consenso
entre modelos) a /api/patient-chat, igual que ya funciona en /api/chat.
Solo informativa (debug_info): no altera la respuesta real al paciente.

Requiere que /api/chat ya tenga verify_claims_with_llm, query_llamafile_response
y compare_with_llamafile disponibles (aplicado por add_dual_model_consensus.py
y add_claim_sanity_filter.py en sesiones anteriores).

Uso:
    python3 scripts/add_patient_chat_verification.py "/ruta/a/backend/main.py"
"""

import sys

ANCHOR = '''    result = {"response": final_response}
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": 8,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fallback_used": fallback_used,
        }
'''

REPLACEMENT = '''    result = {"response": final_response}
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
'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_patient_chat_verification.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if '"llm_unsupported_claims"] = llm_unsupported_claims\n\n            response_b = query_llamafile_response(context_text, request.message)' in content:
        print("Ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(ANCHOR)
    if count == 0:
        print("ABORTADO: no se encontró el bloque esperado en /api/patient-chat. "
              "No se ha escrito nada. Revisa a mano.")
        sys.exit(1)
    if count > 1:
        print(f"ABORTADO: el bloque aparece {count} veces (debería ser único). No se ha escrito nada.")
        sys.exit(1)

    content = content.replace(ANCHOR, REPLACEMENT, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Aplicado correctamente: {path}")


if __name__ == "__main__":
    main()
