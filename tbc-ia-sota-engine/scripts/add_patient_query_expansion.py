#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pieza 5 de 8 (probablemente la ultima real que hacia falta): añade
expand_query() al chat de pacientes, igual que en /api/chat. Ayuda a
encontrar guias en ingles (OMS, CDC, ECDC) aunque la pregunta venga en
español, catalan, arabe o urdu.

LIMITACION CONOCIDA: expand_query() usa un prompt en español que pide
terminos en español e ingles. Si el paciente escribe en arabe o urdu,
la funcion sigue funcionando (el modelo entiende razonablemente bien
instrucciones en un idioma sobre texto en otro), pero no se ha probado
a fondo para esos dos idiomas — igual que el resto de limitaciones ya
documentadas en este proyecto para arabe/urdu.

Uso:
    python3 add_patient_query_expansion.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    retrieval_query = build_retrieval_query(request.message, request.history)
    fragments, metadatas, distances = hybrid_retrieve(retrieval_query, 8)'''

NEW = '''    retrieval_query = build_retrieval_query(request.message, request.history)
    retrieval_query = expand_query(retrieval_query)
    fragments, metadatas, distances = hybrid_retrieve(retrieval_query, 8)'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_patient_query_expansion.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if NEW in content:
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
