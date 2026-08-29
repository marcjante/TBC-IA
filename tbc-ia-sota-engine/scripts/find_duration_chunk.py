#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de DIAGNOSTICO (no modifica nada). Busca directamente en toda la
coleccion de ChromaDB los fragmentos que contengan la frase "6 months"
o "6-month" junto a "regimen" o "treatment", para ver si existe un
fragmento con una afirmacion CLARA y limpia sobre la duracion estandar
del tratamiento, o si esta informacion esta repartida de forma confusa
entre varios trozos sin ninguno que la diga con claridad.

Uso:
    python3 find_duration_chunk.py
"""
import sys
sys.path.insert(0, ".")

from backend.rag import collection

all_data = collection.get(include=["documents", "metadatas"])
docs = all_data["documents"]
metas = all_data["metadatas"]

candidatos = []
for doc, meta in zip(docs, metas):
    lower = doc.lower()
    if ("6-month" in lower or "6 month" in lower or "six-month" in lower) and \
       ("regimen" in lower or "treatment" in lower):
        candidatos.append((doc, meta))

print(f"Fragmentos que mencionan '6 meses' junto a 'regimen/treatment': {len(candidatos)}\n")

for i, (doc, meta) in enumerate(candidatos[:10], start=1):
    print(f"--- Candidato {i} ---")
    print(f"Origen: {meta.get('source')}")
    # Mostrar el trozo de texto alrededor de la mencion de "6 month"
    lower = doc.lower()
    idx = lower.find("6-month")
    if idx == -1:
        idx = lower.find("6 month")
    if idx == -1:
        idx = lower.find("six-month")
    start = max(0, idx - 150)
    end = min(len(doc), idx + 250)
    print("Contexto:", doc[start:end].replace("\n", " "))
    print()
