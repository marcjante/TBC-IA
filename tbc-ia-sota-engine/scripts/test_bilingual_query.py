#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de DIAGNOSTICO (no modifica nada). Comprueba la hipotesis de que
el problema es un desajuste de idioma: la pregunta esta en español, pero
el fragmento correcto esta en ingles ("6-month regimen containing
rifampicin: 2HRZE/4HR"). Si añadir un par de terminos clinicos en ingles
a la consulta hace que ese fragmento aparezca, confirma la hipotesis y
sugiere que ampliar la consulta con vocabulario en ingles (no solo en
español) ayudaria de verdad.

Uso:
    python3 test_bilingual_query.py
"""
import sys
sys.path.insert(0, ".")

from backend.rag import hybrid_retrieve

consultas = [
    "cuanto dura el tratamiento de tuberculosis",
    "cuanto dura el tratamiento de tuberculosis 6-month regimen rifampicin duration",
]

for query in consultas:
    print(f"=== Consulta: {query!r} ===")
    fragments, metadatas, distances = hybrid_retrieve(query, top_k=8)
    encontrado = False
    for frag, meta, dist in zip(fragments, metadatas, distances):
        if "2hrze" in frag.lower() or "6 months of" in frag.lower() or "6-month regimen" in frag.lower():
            encontrado = True
            print(f"  ENCONTRADO en {meta.get('source')} (distancia={dist:.1f})")
    if not encontrado:
        print("  No se encontro el fragmento con la recomendacion clara de 6 meses.")
    print()
