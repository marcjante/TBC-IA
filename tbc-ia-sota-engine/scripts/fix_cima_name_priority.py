#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prioriza en los resultados de cima_search_medication los medicamentos
cuyo NOMBRE COMERCIAL contiene literalmente el termino buscado (los
genericos suelen llamarse igual que el principio activo, ej. "PARACETAMOL
KERN PHARMA"), por delante de marcas sin relacion aparente en el nombre
(ej. "ACTRON", que es un combinado de aspirina+paracetamol+cafeina).

No hace falta ninguna llamada extra a CIMA: es solo un reordenamiento de
los resultados que ya llegan.

Uso:
    python3 fix_cima_name_priority.py "/ruta/a/backend/rag.py"
"""

import sys

OLD = '''    try:
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

NEW = '''    def _prioritize_name_match(resultados, term):
        """Pone primero los medicamentos cuyo nombre comercial contiene
        literalmente el termino buscado (suelen ser el generico "puro"),
        por delante de marcas que no lo mencionan (a menudo combinados
        con otros principios activos, ej. "ACTRON" para "paracetamol")."""
        term_lower = term.lower()
        con_nombre = [r for r in resultados if term_lower in (r.get("nombre") or "").lower()]
        sin_nombre = [r for r in resultados if term_lower not in (r.get("nombre") or "").lower()]
        return con_nombre + sin_nombre

    try:
        resp = requests.get(
            f"{CIMA_BASE}/medicamentos",
            params={"practiv1": name, "pagina": 1},
            timeout=timeout,
        )
        resp.raise_for_status()
        resultados = _parse(resp.json())
        if resultados:
            return _prioritize_name_match(resultados, name)

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
        print("Uso: python3 fix_cima_name_priority.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "_prioritize_name_match" in content:
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
