#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de DIAGNOSTICO. Comprueba directamente, sin pasar por la pagina
web, si un medicamento aparece en:
  1. La bibliografia verificada (tbc_master.db, via query_master_bibliography)
  2. CIMA/AEMPS (via get_drug_safety_info / cima_search_medication)

Prueba varios terminos a la vez (por si hay una confusion de nombre),
para distinguir si el problema es que el dato no existe, o que la
busqueda no lo encuentra por una diferencia de escritura.

Uso:
    python3 check_drug_coverage.py
"""
import sys
sys.path.insert(0, ".")

from backend.rag import query_master_bibliography, get_drug_safety_info, cima_search_medication

TERMINOS_A_PROBAR = ["piperizina", "pirazinamida", "piperazina"]

for termino in TERMINOS_A_PROBAR:
    print(f"{'='*60}")
    print(f"Termino: {termino!r}")
    print(f"{'='*60}")

    print("\n--- Bibliografia verificada (tbc_master.db) ---")
    try:
        resultados_biblio = query_master_bibliography(termino, limit=3)
        if resultados_biblio:
            for r in resultados_biblio:
                print(f"  - {r.get('title', '(sin titulo)')[:80]}")
        else:
            print("  Sin resultados.")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    print("\n--- CIMA / AEMPS ---")
    try:
        resultados_cima = cima_search_medication(termino, limit=3)
        if resultados_cima:
            for r in resultados_cima:
                print(f"  - {r.get('nombre', '(sin nombre)')}")
        else:
            print("  Sin resultados.")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    print()
