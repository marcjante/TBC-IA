#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade un boton "Traduir al castella" en cada tarjeta de resultado de la
busqueda bibliografica, que traduce el resumen usando Ollama (100% local,
sin servicios externos de traduccion) mediante generate_response(), ya
usada en el resto de TBC-AI.

Aplica un unico parche a backend/main.py:
  1. Reescribe renderBiblioResults() para dar a cada tarjeta un boton y
     un hueco donde mostrar la traduccion, guardando los resultados en
     una variable JS para poder recuperarlos al traducir.
  2. Añade la funcion JS translateCard(i).
  3. Añade el endpoint /api/translate.

Uso:
    python3 add_translate_button.py "/ruta/a/backend/main.py"
"""

import sys

JS_OLD = '''    function renderBiblioResults(results, resultsDiv, live) {
      if (!results || !results.length) {
        resultsDiv.innerHTML = '<p>Sense resultats.</p>';
        return;
      }
      const badge = live
        ? '<span style="background:#fef3c7;color:#92400e;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">EN VIU · SENSE VERIFICAR</span>'
        : '<span style="background:#dcfce7;color:#166534;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">VERIFICAT</span>';
      resultsDiv.innerHTML = results.map(r => `
        <div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:10px;">
          <strong>${r.title || ''}</strong>${badge}<br>
          <span style="color:#666;font-size:13px;">${r.journal || 'revista desconeguda'} (${r.year || 's.f.'}) — PMID: ${r.pmid || '-'}</span>
          <p style="font-size:14px;margin-top:8px;">${(r.abstract || '').slice(0, 300)}${(r.abstract || '').length > 300 ? '...' : ''}</p>
          ${r.doi ? `<a href="https://doi.org/${r.doi}" target="_blank">DOI: ${r.doi}</a>` : ''}
        </div>
      `).join('');
    }'''

JS_NEW = '''    let currentBiblioResults = [];

    function renderBiblioResults(results, resultsDiv, live) {
      currentBiblioResults = results || [];
      if (!results || !results.length) {
        resultsDiv.innerHTML = '<p>Sense resultats.</p>';
        return;
      }
      const badge = live
        ? '<span style="background:#fef3c7;color:#92400e;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">EN VIU · SENSE VERIFICAR</span>'
        : '<span style="background:#dcfce7;color:#166534;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">VERIFICAT</span>';
      resultsDiv.innerHTML = results.map((r, i) => `
        <div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:10px;">
          <strong>${r.title || ''}</strong>${badge}<br>
          <span style="color:#666;font-size:13px;">${r.journal || 'revista desconeguda'} (${r.year || 's.f.'}) — PMID: ${r.pmid || '-'}</span>
          <p style="font-size:14px;margin-top:8px;" id="biblio-abstract-${i}">${(r.abstract || '').slice(0, 300)}${(r.abstract || '').length > 300 ? '...' : ''}</p>
          <button onclick="translateCard(${i})"
                  style="font-size:12px;padding:4px 10px;border-radius:6px;border:1px solid #1F4B4C;background:white;color:#1F4B4C;cursor:pointer;margin-bottom:6px;">
            Traduir al castella
          </button>
          <div id="biblio-translated-${i}" style="font-size:14px;color:#333;font-style:italic;margin-bottom:6px;"></div>
          ${r.doi ? `<a href="https://doi.org/${r.doi}" target="_blank">DOI: ${r.doi}</a>` : ''}
        </div>
      `).join('');
    }

    async function translateCard(i) {
      const div = document.getElementById('biblio-translated-' + i);
      const r = currentBiblioResults[i];
      if (!r || !r.abstract) {
        div.textContent = 'No hi ha text per traduir.';
        return;
      }
      div.textContent = 'Traduint (pot trigar uns segons, es fa amb el model local)...';
      try {
        const resp = await fetch('/api/translate?text=' + encodeURIComponent(r.abstract));
        const data = await resp.json();
        div.textContent = data.error ? 'Error en la traduccio.' : data.translated;
      } catch (e) {
        div.textContent = 'Error en la traduccio.';
      }
    }'''

ENDPOINT_OLD = '''@app.get("/api/bibliography-search-live")
def bibliography_search_live(query: str, limit: int = 5):
    """Busca en vivo directamente en PubMed, SIN verificacion de PubTator3
    ni validacion de CrossRef ni deteccion de retracciones (a diferencia
    de /api/bibliography-search). Util cuando la base local no tiene
    resultados para una consulta concreta. Fail-open: lista vacia si falla."""
    try:
        results = search_pubmed_live(query, max_results=limit)
    except Exception:
        results = []
    return {"query": query, "results": results}'''

ENDPOINT_NEW = '''@app.get("/api/bibliography-search-live")
def bibliography_search_live(query: str, limit: int = 5):
    """Busca en vivo directamente en PubMed, SIN verificacion de PubTator3
    ni validacion de CrossRef ni deteccion de retracciones (a diferencia
    de /api/bibliography-search). Util cuando la base local no tiene
    resultados para una consulta concreta. Fail-open: lista vacia si falla."""
    try:
        results = search_pubmed_live(query, max_results=limit)
    except Exception:
        results = []
    return {"query": query, "results": results}


@app.get("/api/translate")
def translate_text(text: str):
    """Traduce un texto (resumen de un articulo) al castellano usando
    Ollama (100% local, sin servicios externos de traduccion). Fail-open:
    devuelve error=True si falla."""
    system_prompt = (
        "Traduce el siguiente texto cientifico-medico (resumen de un articulo "
        "sobre tuberculosis) al castellano. Manten la terminologia clinica "
        "precisa. Responde EXCLUSIVAMENTE con la traduccion, sin comentarios "
        "ni explicaciones adicionales."
    )
    try:
        translated = generate_response(system_prompt, text)
        return {"translated": translated, "error": False}
    except Exception:
        return {"translated": None, "error": True}'''


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
        print("Uso: python3 add_translate_button.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    apply_patch(path, JS_OLD, JS_NEW, "javascript (boton de traduccion)")
    apply_patch(path, ENDPOINT_OLD, ENDPOINT_NEW, "endpoint /api/translate")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
