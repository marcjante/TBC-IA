#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version corregida: la primera version tenia un fallo de busqueda (sin
limite de palabra), por lo que "6 month" coincidia dentro de "36 months"
o "26 months" por accidente. Esta version usa una expresion regular que
exige que el "6" no vaya precedido de otro digito, para encontrar de
verdad menciones a un tratamiento de 6 meses, no cualquier "6" suelto
dentro de otro numero.

Uso:
    python3 find_duration_chunk_v2.py
"""
import sys
import re
sys.path.insert(0, ".")

from backend.rag import collection

all_data = collection.get(include=["documents", "metadatas"])
docs = all_data["documents"]
metas = all_data["metadatas"]

# (?<!\d) = que el caracter anterior NO sea un digito (evita "36 months")
patron = re.compile(r"(?<!\d)6[\s-]month", re.IGNORECASE)

candidatos = []
for doc, meta in zip(docs, metas):
    if patron.search(doc):
        candidatos.append((doc, meta))

print(f"Fragmentos que mencionan de verdad '6 meses' (sin falsos positivos de 36/26...): {len(candidatos)}\n")

for i, (doc, meta) in enumerate(candidatos[:10], start=1):
    print(f"--- Candidato {i} ---")
    print(f"Origen: {meta.get('source')}")
    match = patron.search(doc)
    start = max(0, match.start() - 150)
    end = min(len(doc), match.start() + 250)
    print("Contexto:", doc[start:end].replace("\n", " "))
    print()
