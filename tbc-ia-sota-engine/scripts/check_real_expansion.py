#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de DIAGNOSTICO. Llama directamente a expand_query() (la funcion
real de la aplicacion, no una simulacion) para ver que terminos genera
de verdad el modelo para la pregunta problematica, y si de verdad
incluyo terminos en ingles como se le pidio en el prompt.

Uso (ejecutar desde dentro de main.py como modulo, ya que
expand_query esta definida ahi, no en rag.py):
    python3 check_real_expansion.py
"""
import sys
sys.path.insert(0, ".")

# expand_query esta definida en backend/main.py, junto con el prompt.
# La importamos igual que la importaria main.py al arrancar.
from backend.main import expand_query, build_retrieval_query
from backend.rag import hybrid_retrieve

pregunta = "cuanto dura el tratamiento de tuberculosis"
query_ampliada = expand_query(pregunta)

print(f"Pregunta original: {pregunta!r}")
print(f"Consulta ampliada real: {query_ampliada!r}")
print()

fragments, metadatas, distances = hybrid_retrieve(query_ampliada, top_k=8)
print(f"Con esta consulta ampliada, distancia del mejor resultado: {distances[0]:.1f}" if distances else "Sin resultados")

encontrado = any("2hrze" in f.lower() for f in fragments)
print(f"¿Aparece el fragmento con la recomendacion clara (2HRZE/4HR)? {encontrado}")
