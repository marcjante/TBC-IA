#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige un segundo formato de respuesta de CIMA descubierto con pruebas
reales el 23 de agosto de 2026: mientras que algunas secciones (4.3, 4.5
en el caso probado) devuelven texto plano directo, otras (4.8 en el caso
probado) devuelven una LISTA JSON de objetos con una clave "contenido"
que ademas viene con entidades HTML numericas (&#193; en vez de "Á").

Esta funcion ahora detecta ambos formatos, y _cima_strip_html tambien
decodifica las entidades HTML ademas de quitar las etiquetas.

Uso:
    python3 fix_cima_json_and_entities.py "/ruta/a/backend/rag.py"
"""

import sys

OLD_SECTION = '''def cima_get_ficha_tecnica_section(nregistro, seccion, timeout=10):
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

NEW_SECTION = '''def cima_get_ficha_tecnica_section(nregistro, seccion, timeout=10):
    """Contenido de una seccion concreta de la ficha tecnica oficial
    (tipo=1). CIMA devuelve este endpoint en DOS formatos distintos segun
    la seccion — confirmado con pruebas reales: algunas secciones dan
    texto plano directo (Content-Type: text/plain), otras dan una LISTA
    JSON de objetos con una clave "contenido" (con entidades HTML
    numericas dentro, ej. &#193; en vez de "Á"). Esta funcion detecta
    cual de los dos formatos llego y lo normaliza a texto.

    Fail-open: None si falla o el medicamento no tiene esa seccion."""
    import json as json_module

    try:
        resp = requests.get(
            f"{CIMA_BASE}/docSegmentado/contenido/1",
            params={"nregistro": nregistro, "seccion": seccion},
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.text.strip()
        if not text:
            return None

        # Formato JSON (lista de objetos con "contenido"). CIMA devuelve
        # a veces JSON tecnicamente invalido (saltos de linea sin escapar
        # dentro de las cadenas) — confirmado con pruebas reales, de ahi
        # strict=False para tolerarlo.
        if text.startswith("["):
            try:
                data = json_module.loads(text, strict=False)
                if isinstance(data, list) and data:
                    return data[0].get("contenido")
            except (ValueError, KeyError, IndexError, AttributeError):
                pass

        # Formato texto plano directo
        return text
    except requests.RequestException:
        return None'''

OLD_STRIP = '''def _cima_strip_html(html_text):
    import re
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    return re.sub(r"\\s+", " ", text).strip()'''

NEW_STRIP = '''def _cima_strip_html(html_text):
    """Quita etiquetas HTML y decodifica entidades HTML numericas
    (&#193; -> Á), necesario porque algunas secciones de CIMA (ver
    cima_get_ficha_tecnica_section) devuelven el contenido asi codificado."""
    import re
    import html as html_module
    if not html_text:
        return ""
    text = html_module.unescape(html_text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\\s+", " ", text).strip()'''


def apply_patch(path, old, new, label):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if new in content:
        print(f"  {label}: ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(old)
    if count == 0:
        print(f"  {label}: ABORTADO, no se encontró el bloque esperado. No se ha escrito nada.")
        sys.exit(1)
    if count > 1:
        print(f"  {label}: ABORTADO, el bloque aparece {count} veces (debería ser único). No se ha escrito nada.")
        sys.exit(1)

    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  {label}: aplicado correctamente.")


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 fix_cima_json_and_entities.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    apply_patch(path, OLD_SECTION, NEW_SECTION, "cima_get_ficha_tecnica_section (dos formatos)")
    apply_patch(path, OLD_STRIP, NEW_STRIP, "_cima_strip_html (entidades HTML)")

    print("\nHecho. Prueba de nuevo con python3 (sin necesidad de reiniciar el servidor todavia).")


if __name__ == "__main__":
    main()
