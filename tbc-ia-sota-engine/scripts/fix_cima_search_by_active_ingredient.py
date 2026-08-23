#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige cima_search_medication(): el parametro "nombre" de la API de CIMA
busca solo por NOMBRE COMERCIAL del medicamento (ej. "Rimactan"), no por
principio activo (ej. "rifampicina") — confirmado con pruebas reales el
23 de agosto de 2026 (0 resultados con nombre=rifampicina, 7 resultados
con practiv1=rifampicina).

Ahora prueba primero por principio activo (caso mas habitual: alguien
escribe el nombre generico del farmaco), y si no encuentra nada, prueba
tambien por nombre comercial.

Uso:
    python3 fix_cima_search_by_active_ingredient.py "/ruta/a/backend/rag.py"
"""

import sys

OLD = '''def cima_search_medication(name, limit=10, timeout=10):
    """Busca medicamentos en CIMA por nombre (comercial o principio
    activo). Fail-open: lista vacia si falla."""
    try:
        resp = requests.get(
            f"{CIMA_BASE}/medicamentos",
            params={"nombre": name, "pagina": 1},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        resultados = data.get("resultados", [])[:limit]
        return [{
            "nregistro": r.get("nregistro"),
            "nombre": r.get("nombre"),
            "laboratorio": r.get("labtitular"),
            "comercializado": r.get("comerc"),
        } for r in resultados]
    except (requests.RequestException, ValueError, KeyError):
        return []'''

NEW = '''def cima_search_medication(name, limit=10, timeout=10):
    """Busca medicamentos en CIMA. El parametro "nombre" de la API de CIMA
    busca SOLO por nombre comercial (ej. "Rimactan"), no por principio
    activo (ej. "rifampicina") — confirmado con pruebas reales. Por eso
    se prueba primero por principio activo (practiv1, el caso mas
    habitual: alguien escribe el nombre generico del farmaco), y solo si
    no hay resultados se prueba por nombre comercial.

    Fail-open: lista vacia si falla."""
    def _parse(data):
        return [{
            "nregistro": r.get("nregistro"),
            "nombre": r.get("nombre"),
            "laboratorio": r.get("labtitular"),
            "comercializado": r.get("comerc"),
        } for r in data.get("resultados", [])[:limit]]

    try:
        resp = requests.get(
            f"{CIMA_BASE}/medicamentos",
            params={"practiv1": name, "pagina": 1},
            timeout=timeout,
        )
        resp.raise_for_status()
        resultados = _parse(resp.json())
        if resultados:
            return resultados

        # Sin resultados por principio activo: probar por nombre comercial
        resp2 = requests.get(
            f"{CIMA_BASE}/medicamentos",
            params={"nombre": name, "pagina": 1},
            timeout=timeout,
        )
        resp2.raise_for_status()
        return _parse(resp2.json())
    except (requests.RequestException, ValueError, KeyError):
        return []'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 fix_cima_search_by_active_ingredient.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "practiv1" in content:
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
