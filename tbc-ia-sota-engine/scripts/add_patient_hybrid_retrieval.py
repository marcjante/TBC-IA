#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pieza 3 de 8: porta al chat de pacientes las tres mejoras de retrieval
que ya funcionan en /api/chat:
  1. hybrid_retrieve() en vez de retrieve() (BM25 + semantico con
     fusion RRF, ya con el reequilibrio de pesos y la correccion de
     suficiencia aplicados en rag.py — se heredan automaticamente al
     cambiar de funcion, sin duplicar nada).
  2. Priorizacion de fuentes clinicas (OMS, CDC) sobre vigilancia
     epidemiologica en el contexto que ve el generador.
  3. Limite de fuentes para el generador (7, igual que /api/chat) para
     mantener el mismo margen de velocidad.

Uso:
    python3 add_patient_hybrid_retrieval.py "/ruta/a/backend/main.py"
"""

import sys

OLD_1 = '''    retrieval_query = build_retrieval_query(request.message, request.history)
    fragments, metadatas, distances = retrieve(retrieval_query, 8)'''

NEW_1 = '''    retrieval_query = build_retrieval_query(request.message, request.history)
    fragments, metadatas, distances = hybrid_retrieve(retrieval_query, 8)'''

OLD_2 = '''    context_parts = [frag for frag in fragments]
    context_text = "\\n\\n---\\n\\n".join(context_parts)
    history_block = build_history_block(request.history)'''

NEW_2 = '''    # Priorizar fuentes clinicas (OMS, CDC) sobre vigilancia
    # epidemiologica, mismo criterio que /api/chat (hallazgo del 23 de
    # agosto de 2026: documentos de vigilancia usan "tratamiento" y
    # "meses" en un sentido distinto al clinico y pueden diluir la
    # señal correcta).
    CLINICAL_CATEGORIES_PATIENT = {"01_WHO", "02_CDC", "05_ClinicalKB_JSON"}
    paired = list(zip(fragments, metadatas))
    paired.sort(key=lambda par: 0 if par[1].get("category") in CLINICAL_CATEGORIES_PATIENT else 1)
    fragments = [par[0] for par in paired]
    metadatas = [par[1] for par in paired]

    # Limitar cuantas fuentes ve el generador (mismo margen que /api/chat).
    MAX_SOURCES_FOR_GENERATION_PATIENT = 7
    context_parts = [frag for frag in fragments[:MAX_SOURCES_FOR_GENERATION_PATIENT]]
    context_text = "\\n\\n---\\n\\n".join(context_parts)
    history_block = build_history_block(request.history)'''


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
        print("Uso: python3 add_patient_hybrid_retrieval.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    for old, new, label in [
        (OLD_1, NEW_1, "hybrid_retrieve en patient_chat"),
        (OLD_2, NEW_2, "priorizacion clinica + limite de fuentes"),
    ]:
        content, _ = apply_patch(path, old, new, label)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
