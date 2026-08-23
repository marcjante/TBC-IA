#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade a la pagina principal de TBC-AI (/) una tarjeta con un punto de
color que indica si el Panel TBC-IA (puerto 8090) esta conectado o no,
comprobado desde el propio servidor via un nuevo endpoint /api/panel-status
(evita problemas de CORS del navegador al consultar otro puerto).

Uso:
    python3 scripts/add_panel_indicator.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''    <a class="card" href="/patient/">
      <span class="tag patient">Pacients</span>
      <h2>Seguiment TBC · ITL</h2>
      <p>Xat de triatge amb pacients en tractament, historial de missatges i panell professional de seguiment.</p>
      <div class="status"><span class="dot"></span>Firestore · en linia</div>
    </a>
    <a class="card" href="/guides/">
      <span class="tag clinic">Clinic</span>
      <h2>TBC-AI</h2>
      <p>Assistent sobre guies cliniques de l'OMS, CDC i ECDC, amb cita de font i pagina en cada resposta.</p>
      <div class="status"><span class="dot"></span>Ollama · {CHAT_MODEL_PLACEHOLDER}</div>
    </a>
  </div>

  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
</body>
</html>
"""
    return html.replace("{CHAT_MODEL_PLACEHOLDER}", CHAT_MODEL)'''

NEW = '''    <a class="card" href="/patient/">
      <span class="tag patient">Pacients</span>
      <h2>Seguiment TBC · ITL</h2>
      <p>Xat de triatge amb pacients en tractament, historial de missatges i panell professional de seguiment.</p>
      <div class="status"><span class="dot"></span>Firestore · en linia</div>
    </a>
    <a class="card" href="/guides/">
      <span class="tag clinic">Clinic</span>
      <h2>TBC-AI</h2>
      <p>Assistent sobre guies cliniques de l'OMS, CDC i ECDC, amb cita de font i pagina en cada resposta.</p>
      <div class="status"><span class="dot"></span>Ollama · {CHAT_MODEL_PLACEHOLDER}</div>
    </a>
    <a class="card" href="http://127.0.0.1:8090" target="_blank">
      <span class="tag clinic">Sistema</span>
      <h2>Panel TBC-IA</h2>
      <p>Estat en temps real dels set serveis (Ollama, motor complementari, Llamafile, n8n, bibliografia...).</p>
      <div class="status"><span class="dot" id="panel-dot" style="background:#888;"></span><span id="panel-text">Comprovant...</span></div>
    </a>
  </div>

  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
  <script>
    fetch('/api/panel-status').then(r => r.json()).then(d => {
      const dot = document.getElementById('panel-dot');
      const text = document.getElementById('panel-text');
      if (d.connected) {
        dot.style.background = '#4ade80';
        text.textContent = 'Panel connectat';
      } else {
        dot.style.background = '#f87171';
        text.textContent = 'Panel no connectat';
      }
    }).catch(() => {
      document.getElementById('panel-text').textContent = 'Panel no connectat';
    });
  </script>
</body>
</html>
"""
    return html.replace("{CHAT_MODEL_PLACEHOLDER}", CHAT_MODEL)


@app.get("/api/panel-status")
def panel_status():
    """Comprueba desde el propio servidor (no desde el navegador, para
    evitar problemas de CORS) si el Panel TBC-IA (puerto 8090) esta
    conectado. Fail-open: devuelve connected=False si no responde."""
    import requests
    try:
        resp = requests.get("http://127.0.0.1:8090", timeout=1.5)
        return {"connected": resp.status_code == 200}
    except requests.RequestException:
        return {"connected": False}'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_panel_indicator.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "/api/panel-status" in content:
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
