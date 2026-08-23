#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige cima_get_ficha_tecnica_section(): el endpoint
/docSegmentado/contenido/1 de CIMA devuelve el contenido como TEXTO PLANO
directo (Content-Type: text/plain), no como JSON con una clave
"contenido" como se asumio al escribir la funcion — confirmado con
pruebas reales el 23 de agosto de 2026 (JSONDecodeError al intentar
.json() sobre la respuesta real).

Uso:
    python3 fix_cima_section_plain_text.py "/ruta/a/backend/rag.py"
"""

import sys

OLD = '''def cima_get_ficha_tecnica_section(nregistro, seccion, timeout=10):
    """Contenido (HTML) de una seccion concreta de la ficha tecnica
    oficial (tipo=1). Fail-open: None si falla."""
    try:
        resp = requests.get(
            f"{CIMA_BASE}/docSegmentado/contenido/1",
            params={"nregistro": nregistro, "seccion": seccion},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("contenido")
    except (requests.RequestException, ValueError, KeyError):
        return None'''

NEW = '''def cima_get_ficha_tecnica_section(nregistro, seccion, timeout=10):
    """Contenido de una seccion concreta de la ficha tecnica oficial
    (tipo=1). CIMA devuelve este endpoint como TEXTO PLANO directo
    (Content-Type: text/plain), NO como JSON — confirmado con pruebas
    reales (antes se asumia .json().get("contenido"), que fallaba con
    JSONDecodeError). Fail-open: None si falla o el medicamento no tiene
    esa seccion."""
    try:
        resp = requests.get(
            f"{CIMA_BASE}/docSegmentado/contenido/1",
            params={"nregistro": nregistro, "seccion": seccion},
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.text.strip()
        # CIMA a veces devuelve un mensaje de error o vacio si la seccion
        # no existe para ese medicamento concreto (no todos la tienen).
        if not text:
            return None
        return text
    except requests.RequestException:
        return None'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 fix_cima_section_plain_text.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if 'Content-Type: text/plain' in content:
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
