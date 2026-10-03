#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Panel de control unico: una sola pagina web donde ver de un vistazo el
estado de los seis servicios del stack TBC-IA (Ollama, motor
complementario, TBC-AI, Llamafile, n8n, bibliografia verificada).

No sustituye a status_tbc_stack.sh (ese sigue siendo util desde terminal),
esto es la misma informacion pero en una pagina web que se puede dejar
abierta y se actualiza sola cada 5 segundos.

Uso:
    cd ~/Desktop/"TBC IA"/dashboard
    source venv/bin/activate
    pip install fastapi uvicorn requests
    python3 dashboard_service.py

Luego abre: http://127.0.0.1:8090
"""

import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Panel TBC-IA")

SERVICES = [
    {"name": "Ollama", "port": 11434, "url": "http://127.0.0.1:11434", "link": "http://127.0.0.1:11434", "desc": "Modelo Llama 3.1 8B"},
    {"name": "Motor complementario", "port": 8003, "url": "http://127.0.0.1:8003", "link": "http://127.0.0.1:8003", "desc": "Recuperacion hibrida + verificacion"},
    {"name": "TBC-AI", "port": 8001, "url": "http://127.0.0.1:8001/api/health", "link": "http://127.0.0.1:8001", "desc": "Backend principal (chat profesional y pacientes)"},
    {"name": "Llamafile / Mistral", "port": 8081, "url": "http://127.0.0.1:8081/health", "link": "http://127.0.0.1:8081", "desc": "Segundo modelo (consenso entre modelos)"},
    {"name": "n8n", "port": 5678, "url": "http://127.0.0.1:5678", "link": "http://127.0.0.1:5678", "desc": "Automatizaciones (copias de seguridad, harvester)"},
    {"name": "Bibliografia TBC", "port": 8002, "url": "http://127.0.0.1:8002/health", "link": "http://127.0.0.1:8002", "desc": "PubMed + Europe PMC + PubTator3 + CrossRef"},
]


def check_service(svc, timeout=2):
    try:
        resp = requests.get(svc["url"], timeout=timeout)
        return {"status": "ok", "http_code": resp.status_code}
    except requests.RequestException:
        return {"status": "down", "http_code": None}


@app.get("/api/status")
def api_status():
    results = []
    for svc in SERVICES:
        check = check_service(svc)
        results.append({
            "name": svc["name"],
            "port": svc["port"],
            "desc": svc["desc"],
            "link": svc["link"],
            "status": check["status"],
            "http_code": check["http_code"],
        })
    return JSONResponse({"services": results})


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panel TBC-IA</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%231F4B4C'/%3E%3Cpath d='M10,50 L35,50 L42,30 L50,70 L58,50 L90,50' stroke='%233E8E89' stroke-width='7' fill='none' stroke-linecap='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #EEF3F0;
    --surface: #FFFFFF;
    --ink: #152623;
    --ink-soft: #4A5B57;
    --teal: #1F6F72;
    --teal-dark: #123F42;
    --coral: #B8433A;
    --coral-bg: #FBEAE8;
    --sage: #4F8562;
    --sage-bg: #E9F2EA;
    --line: #D7E0DB;
  }
  * { box-sizing: border-box; }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--ink);
    margin: 0;
    padding: 40px 20px;
    -webkit-font-smoothing: antialiased;
  }
  h1 {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    text-align: center;
    font-size: 28px;
    margin: 0 0 4px;
    letter-spacing: -0.01em;
  }
  .subtitle {
    text-align: center;
    color: var(--ink-soft);
    margin-bottom: 24px;
    font-size: 14px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    max-width: 1000px;
    margin: 0 auto;
  }
  .card {
    background: var(--surface);
    border-radius: 10px;
    padding: 20px;
    border: 1px solid var(--line);
    border-left: 3px solid var(--line);
    transition: border-color 0.3s;
  }
  .card.ok { border-left-color: var(--sage); }
  .card.down { border-left-color: var(--coral); }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .name { font-weight: 600; font-size: 16px; }
  .badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: .03em;
  }
  .badge.ok { background: var(--sage-bg); color: var(--sage); }
  .badge.down { background: var(--coral-bg); color: var(--coral); }
  .desc { color: var(--ink-soft); font-size: 13px; margin-bottom: 8px; }
  .port { color: var(--ink-soft); font-size: 12px; font-family: 'IBM Plex Mono', monospace; }
  .updated {
    text-align: center;
    color: var(--ink-soft);
    font-size: 12px;
    margin-top: 32px;
  }
  button:focus-visible, a:focus-visible {
    outline: 2px solid var(--teal-dark);
    outline-offset: 2px;
  }
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
  }
  @media (max-width: 480px) {
    body { padding: 28px 14px; }
  }
</style>
</head>
<body>
  <h1>Panel TBC-IA</h1>
  <div class="subtitle">Estado de los servicios en tiempo real</div>

  <div class="grid" id="grid">Cargando...</div>
  <div class="updated" id="updated"></div>

  <script>
    async function refresh() {
      try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        const grid = document.getElementById('grid');
        grid.innerHTML = data.services.map(svc => `
          <div class="card ${svc.status}">
            <div class="card-header">
              <span class="name">${svc.name}</span>
              <span class="badge ${svc.status}">${svc.status === 'ok' ? 'OK' : 'NO RESPONDE'}</span>
            </div>
            <div class="desc">${svc.desc}</div>
            <div class="port">puerto ${svc.port}</div>
          </div>
        `).join('');
        document.getElementById('updated').textContent =
          'Actualizado: ' + new Date().toLocaleTimeString('es-ES');
      } catch (e) {
        document.getElementById('grid').innerHTML =
          '<div class="card down">No se pudo conectar con el panel</div>';
      }
    }
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


if __name__ == "__main__":
    import uvicorn
    print("Panel TBC-IA disponible en: http://127.0.0.1:8090")
    uvicorn.run(app, host="127.0.0.1", port=8090)
