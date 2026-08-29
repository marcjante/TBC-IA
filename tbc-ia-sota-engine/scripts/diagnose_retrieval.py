#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de DIAGNOSTICO (no modifica nada de la aplicacion). Llama
directamente a hybrid_retrieve() con la pregunta problematica de esta
noche y muestra que fuentes trae de verdad, para ver si la informacion
sobre duracion del tratamiento esta realmente entre ellas o no.

Uso (desde la carpeta TBC IA, con el venv activado):
    python3 tbc-ia-sota-engine/scripts/diagnose_retrieval.py
"""
import sys
sys.path.insert(0, ".")

from backend.rag import hybrid_retrieve

query = "cuanto dura el tratamiento de tuberculosis"
fragments, metadatas, distances = hybrid_retrieve(query, top_k=8)

print(f"Pregunta: {query!r}")
print(f"Numero de fuentes devueltas: {len(fragments)}\n")

for i, (frag, meta, dist) in enumerate(zip(fragments, metadatas, distances), start=1):
    print(f"--- Fuente {i} (distancia={dist:.1f}) ---")
    print(f"Origen: {meta.get('source')}")
    print(f"Categoria: {meta.get('category')}")
    print(f"Texto (primeros 300 caracteres):")
    print(frag[:300].replace("\n", " "))
    print()
