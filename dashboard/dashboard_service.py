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
    cd ~/Desktop/"TBC IA"/tbc-master-database   (o donde prefieras)
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
    {"name": "Ollama", "port": 11434, "url": "http://127.0.0.1:11434", "desc": "Modelo Llama 3.1 8B"},
    {"name": "Motor complementario", "port": 8000, "url": "http://127.0.0.1:8000", "desc": "Recuperacion hibrida + verificacion"},
    {"name": "TBC-AI", "port": 8001, "url": "http://127.0.0.1:8001/api/health", "desc": "Backend principal (chat profesional y pacientes)"},
    {"name": "Llamafile / Mistral", "port": 8081, "url": "http://127.0.0.1:8081/health", "desc": "Segundo modelo (consenso entre modelos)"},
    {"name": "n8n", "port": 5678, "url": "http://127.0.0.1:5678", "desc": "Automatizaciones (copias de seguridad, harvester)"},
    {"name": "Bibliografia TBC", "port": 8002, "url": "http://127.0.0.1:8002/health", "desc": "PubMed + Europe PMC + PubTator3 + CrossRef"},
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
            "status": check["status"],
            "http_code": check["http_code"],
        })
    return JSONResponse({"services": results})


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Panel TBC-IA</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0f1117;
    color: #e6e6e6;
    margin: 0;
    padding: 40px 20px;
  }
  h1 {
    text-align: center;
    font-weight: 600;
    margin-bottom: 4px;
  }
  .subtitle {
    text-align: center;
    color: #9098a8;
    margin-bottom: 32px;
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
    background: #1a1d27;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #2a2e3a;
    transition: border-color 0.3s;
  }
  .card.ok { border-color: #2e8b57; }
  .card.down { border-color: #b34545; }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .name { font-weight: 600; font-size: 16px; }
  .badge {
    font-size: 12px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 20px;
  }
  .badge.ok { background: #14351f; color: #4ade80; }
  .badge.down { background: #3a1414; color: #f87171; }
  .desc { color: #9098a8; font-size: 13px; margin-bottom: 8px; }
  .port { color: #6b7280; font-size: 12px; font-family: monospace; }
  .updated {
    text-align: center;
    color: #6b7280;
    font-size: 12px;
    margin-top: 32px;
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
