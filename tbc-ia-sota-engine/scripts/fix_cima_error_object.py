#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige un hallazgo real del 23 de agosto de 2026 (captura de pantalla
con "Clofazimina" / Lampren capsulas): cuando CIMA no tiene una seccion
concreta de la ficha tecnica para un medicamento, a veces devuelve un
OBJETO JSON de error, ej. {"error":"No existen secciones para el
medicamento indicado"} — que empieza por "{", no por "[".

cima_get_ficha_tecnica_section() solo comprobaba el formato de LISTA
JSON (texto que empieza por "["); el objeto de error caia en la rama de
"texto plano directo" y se devolvia tal cual como si fuera contenido
real, colandose hasta la interfaz en vez del "no disponible" que ya
funciona bien para otras secciones (fail-open documentado mal cumplido).

Uso:
    python3 fix_cima_error_object.py "/ruta/a/backend/rag.py"
"""

import sys

OLD = '''        if text.startswith("["):
            try:
                data = json_module.loads(text, strict=False)
                if isinstance(data, list) and data:
                    return data[0].get("contenido")
            except (ValueError, KeyError, IndexError, AttributeError):
                pass

        # Formato texto plano directo
        return text'''

NEW = '''        if text.startswith("["):
            try:
                data = json_module.loads(text, strict=False)
                if isinstance(data, list) and data:
                    return data[0].get("contenido")
            except (ValueError, KeyError, IndexError, AttributeError):
                pass

        # Objeto de error de CIMA cuando el medicamento no tiene esta
        # seccion, ej. {"error":"No existen secciones para el
        # medicamento indicado"}. Empieza por "{", no por "[", asi que
        # no entraba en la comprobacion de arriba y se colaba como si
        # fuera texto real (hallazgo del 23 de agosto de 2026). Se trata
        # igual que "sin contenido", cumpliendo el fail-open ya
        # documentado en esta funcion.
        if text.startswith("{"):
            try:
                data = json_module.loads(text, strict=False)
                if isinstance(data, dict) and "error" in data:
                    return None
            except (ValueError, AttributeError):
                pass

        # Formato texto plano directo
        return text'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 fix_cima_error_object.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if 'text.startswith("{")' in content:
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
