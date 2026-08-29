#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige un hallazgo real del 23 de agosto de 2026: con la fusion RRF a
partes iguales, documentos de vigilancia epidemiologica (ECDC, planes
nacionales, RENAVE) que repiten mucho las palabras "tratamiento" y
"meses" en un sentido totalmente distinto (plazos de notificacion a
las autoridades, no duracion clinica) desplazaban a la guia clinica de
la OMS que si contesta bien preguntas como "cuanto dura el tratamiento
de tuberculosis" — que antes de tener retrieval hibrido, solo con
busqueda semantica, SI se encontraba correctamente.

Diagnostico confirmado con pruebas reales (diagnose_retrieval.py): la
guia de la OMS con la respuesta correcta no aparecia entre las 8
fuentes fusionadas, todas ellas documentos de vigilancia.

Arreglo: BM25 sigue aportando valor real (sigue pudiendo encontrar
fuentes que la busqueda semantica por si sola no traeria, como se vio
con el caso de etambutol), pero con la mitad de peso en la fusion, para
que ya no pueda por si solo desplazar a un resultado semantico fuerte.

Uso:
    python3 weight_semantic_over_bm25.py "/ruta/a/backend/rag.py"
"""

import sys

OLD = '''    # --- Fusion RRF por id ---
    k_rrf = 60
    rrf_scores = {}
    for rank, doc_id in enumerate(dense_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)
    for rank, doc_id in enumerate(bm25_ranked_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)'''

NEW = '''    # --- Fusion RRF por id, con la busqueda semantica pesando mas ---
    # Hallazgo del 23 de agosto de 2026: con peso igual, documentos de
    # vigilancia epidemiologica (que repiten mucho "tratamiento" y
    # "meses" en un sentido distinto: plazos de notificacion, no
    # duracion clinica) desplazaban a la guia clinica correcta de la
    # OMS. BM25_WEIGHT=0.5 deja que BM25 siga aportando fuentes que la
    # busqueda semantica por si sola no encontraria (ver caso etambutol
    # de esta noche), pero sin que pueda por si solo tapar un resultado
    # semantico fuerte.
    k_rrf = 60
    BM25_WEIGHT = 0.5
    rrf_scores = {}
    for rank, doc_id in enumerate(dense_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)
    for rank, doc_id in enumerate(bm25_ranked_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + BM25_WEIGHT / (k_rrf + rank + 1)'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 weight_semantic_over_bm25.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "BM25_WEIGHT" in content:
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
