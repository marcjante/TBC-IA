#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script de DIAGNOSTICO: en que posicion exacta (1-8) queda el
fragmento con la recomendacion clara de 6 meses, con la consulta ya
ampliada de verdad por expand_query()."""
import sys
sys.path.insert(0, ".")

from backend.main import expand_query
from backend.rag import hybrid_retrieve

pregunta = "cuanto dura el tratamiento de tuberculosis"
query_ampliada = expand_query(pregunta)

fragments, metadatas, distances = hybrid_retrieve(query_ampliada, top_k=8)

for i, (frag, meta, dist) in enumerate(zip(fragments, metadatas, distances), start=1):
    marca = " <-- ESTE ES" if "2hrze" in frag.lower() else ""
    print(f"Posicion {i}: {meta.get('source')} (distancia={dist:.1f}){marca}")
