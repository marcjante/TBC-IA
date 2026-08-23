#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige un fallo real encontrado el 23 de agosto de 2026: _parse()
recortaba a los primeros `limit` resultados ANTES de aplicar la
priorizacion por nombre, y CIMA devuelve sus resultados ordenados
alfabeticamente por marca comercial — asi que para "paracetamol" (418
resultados), los primeros 10 son marcas que empiezan por "A" (Actron,
Antidol...), ninguna de las cuales se llama "Paracetamol algo". Los
genericos "PARACETAMOL X" existen mas abajo en la lista completa, pero
nunca llegaban a evaluarse porque ya se habia recortado antes.

Ahora se recorta DESPUES de reordenar por prioridad de nombre, sobre el
conjunto completo que devuelve CIMA en esa pagina (hasta 200 resultados).

Uso:
    python3 fix_cima_limit_after_priority.py "/ruta/a/backend/rag.py"
"""

import sys

OLD = '''    def _parse(data):
        return [{
            "nregistro": r.get("nregistro"),
            "nombre": r.get("nombre"),
            "laboratorio": r.get("labtitular"),
            "comercializado": r.get("comerc"),
        } for r in data.get("resultados", [])[:limit]]

    def _prioritize_name_match(resultados, term):
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

NEW = '''    def _parse(data):
        # IMPORTANTE: no recortar aqui a "limit" — CIMA devuelve sus
        # resultados ordenados alfabeticamente por marca comercial, asi
        # que recortar antes de priorizar por nombre dejaria fuera los
        # genericos "PARACETAMOL X" si empiezan por una letra mas
        # avanzada que las marcas comerciales (ej. "ACTRON", "ANTIDOL").
        # Se recorta al final, despues de reordenar por prioridad.
        return [{
            "nregistro": r.get("nregistro"),
            "nombre": r.get("nombre"),
            "laboratorio": r.get("labtitular"),
            "comercializado": r.get("comerc"),
        } for r in data.get("resultados", [])]

    def _prioritize_name_match(resultados, term):
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
            return _prioritize_name_match(resultados, name)[:limit]

        # Sin resultados por principio activo: probar por nombre comercial
        resp2 = requests.get(
            f"{CIMA_BASE}/medicamentos",
            params={"nombre": name, "pagina": 1},
            timeout=timeout,
        )
        resp2.raise_for_status()
        return _parse(resp2.json())[:limit]
    except (requests.RequestException, ValueError, KeyError):
        return []'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 fix_cima_limit_after_priority.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "no recortar aqui a" in content:
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
