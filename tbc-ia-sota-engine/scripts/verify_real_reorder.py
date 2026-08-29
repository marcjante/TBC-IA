#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script de DIAGNOSTICO: confirma que, en el pipeline real (usando las
mismas funciones que usa /api/chat), la fuente clinica correcta queda
de verdad en primera posicion tras el reordenamiento."""
import sys
sys.path.insert(0, ".")

from backend.main import expand_query
from backend.rag import hybrid_retrieve

pregunta = "cuanto dura el tratamiento de tuberculosis"
query_ampliada = expand_query(pregunta)
fragments, metadatas, distances = hybrid_retrieve(query_ampliada, top_k=8)

CLINICAL_CATEGORIES = {"01_WHO", "02_CDC", "05_ClinicalKB_JSON"}
paired = list(zip(fragments, metadatas))
paired.sort(key=lambda par: 0 if par[1].get("category") in CLINICAL_CATEGORIES else 1)

print("Orden tras el reordenamiento (igual que veria el generador):")
for i, (frag, meta) in enumerate(paired, 1):
    marca = " <-- RESPUESTA CORRECTA" if "2hrze" in frag.lower() else ""
    print(f"  {i}. {meta.get('source')} ({meta.get('category')}){marca}")
