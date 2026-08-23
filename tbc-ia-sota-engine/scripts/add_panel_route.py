#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade una ruta /panel a TBC-AI (puerto 8001) que muestra incrustado el
Panel TBC-IA (puerto 8090), para poder ver de un vistazo si el panel de
estado esta funcionando, sin salir de TBC-AI.

Uso:
    python3 scripts/add_panel_route.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''@app.get("/", response_class=HTMLResponse)
def home():'''

NEW = '''@app.get("/panel", response_class=HTMLResponse)
def panel():
    """Muestra incrustado el Panel TBC-IA (puerto 8090) con el estado de
    los siete servicios, para verlo sin salir de TBC-AI. Si el panel no
    esta corriendo, se ve un mensaje de error dentro del propio iframe
    (no rompe esta pagina)."""
    return """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Panel TBC-IA (incrustado)</title>
<style>
  body { margin: 0; padding: 0; background: #0f1117; }
  .topbar {
    background: #1a1d27; color: #9098a8; padding: 10px 20px;
    font-family: -apple-system, sans-serif; font-size: 13px;
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1px solid #2a2e3a;
  }
  .topbar a { color: #4ade80; text-decoration: none; }
  iframe { width: 100%; height: calc(100vh - 41px); border: none; }
</style>
</head>
<body>
  <div class="topbar">
    <span>Panel TBC-IA — vista incrustada (puerto 8090)</span>
    <a href="http://127.0.0.1:8090" target="_blank">Abrir en pestaña aparte ↗</a>
  </div>
  <iframe src="http://127.0.0.1:8090"></iframe>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_panel_route.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if '@app.get("/panel"' in content:
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
