#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade a la pagina principal de TBC-AI (/) una caja de busqueda que
consulta la bibliografia verificada directamente (via query_master_bibliography,
ya importada en main.py desde la integracion de hoy) — sin pasar por el
puerto 8002, mas directo y sin problemas de CORS.

Requiere que add_panel_indicator.py ya se haya aplicado antes (esta
pensado para encadenarse justo despues).

Uso:
    python3 scripts/add_biblio_search.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
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

NEW = '''  <div class="biblio-search-section" style="max-width:900px;margin:40px auto;padding:0 20px;">
    <h2 style="margin-bottom:12px;">Cerca a la bibliografia verificada</h2>
    <div style="display:flex;gap:8px;margin-bottom:16px;">
      <input id="biblio-query" type="text" placeholder="p.ex. isoniazid resistance"
             style="flex:1;padding:10px;border-radius:6px;border:1px solid #ccc;font-size:14px;"
             onkeydown="if(event.key==='Enter') searchBiblio()">
      <button onclick="searchBiblio()"
              style="padding:10px 20px;border-radius:6px;border:none;background:#1F4B4C;color:white;cursor:pointer;font-size:14px;">
        Cercar
      </button>
    </div>
    <div id="biblio-results"></div>
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

    async function searchBiblio() {
      const q = document.getElementById('biblio-query').value.trim();
      const resultsDiv = document.getElementById('biblio-results');
      if (!q) return;
      resultsDiv.innerHTML = '<p>Cercant...</p>';
      try {
        const resp = await fetch('/api/bibliography-search?query=' + encodeURIComponent(q) + '&limit=5');
        const data = await resp.json();
        if (!data.results || !data.results.length) {
          resultsDiv.innerHTML = '<p>Sense resultats.</p>';
          return;
        }
        resultsDiv.innerHTML = data.results.map(r => `
          <div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:10px;">
            <strong>${r.title || ''}</strong><br>
            <span style="color:#666;font-size:13px;">${r.journal || 'revista desconeguda'} (${r.year || 's.f.'}) — PMID: ${r.pmid || '-'}</span>
            <p style="font-size:14px;margin-top:8px;">${(r.abstract || '').slice(0, 300)}${(r.abstract || '').length > 300 ? '...' : ''}</p>
            ${r.doi ? `<a href="https://doi.org/${r.doi}" target="_blank">DOI: ${r.doi}</a>` : ''}
          </div>
        `).join('');
      } catch (e) {
        resultsDiv.innerHTML = '<p>Error consultant la bibliografia.</p>';
      }
    }
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
        return {"connected": False}


@app.get("/api/bibliography-search")
def bibliography_search(query: str, limit: int = 5):
    """Busca en la bibliografia verificada (tbc_master.db) directamente,
    sin pasar por el puerto 8002 (reutiliza query_master_bibliography, ya
    usada en /api/chat). Fail-open: devuelve lista vacia si falla."""
    try:
        results = query_master_bibliography(query, limit=limit)
    except Exception:
        results = []
    results = [r for r in results if r.get("retraction_status") == "ninguna"]
    return {"query": query, "results": results}'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_biblio_search.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "/api/bibliography-search" in content:
        print("Ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(OLD)
    if count == 0:
        print("ABORTADO: no se encontró el bloque esperado (¿se aplicó ya add_panel_indicator.py?). "
              "No se ha escrito nada.")
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
