#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fusiona la busqueda de CIMA (AEMPS) dentro del boton "Cercar (base
verificada)", ya que ambas son fuentes oficiales/verificadas — en vez de
tener un tercer boton separado. Un solo clic busca en tbc_master.db
(bibliografia) Y en CIMA (medicamentos) a la vez, mostrando ambos tipos
de resultado juntos, marcados como "VERIFICAT".

Quita el boton "Cercar a CIMA (AEMPS)" del HTML (la funcion searchAemps()
se queda definida pero sin usar, no hace falta borrarla).

Uso:
    python3 merge_cima_into_verified_search.py "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# PARCHE 1: quitar el tercer boton
# ---------------------------------------------------------------

HTML_OLD = '''      <button onclick="searchBiblioLive()"
              style="padding:10px 20px;border-radius:6px;border:1px solid #1F4B4C;background:white;color:#1F4B4C;cursor:pointer;font-size:14px;">
        Cercar en viu a PubMed
      </button>
      <button onclick="searchAemps()"
              style="padding:10px 20px;border-radius:6px;border:1px solid #3730a3;background:white;color:#3730a3;cursor:pointer;font-size:14px;">
        Cercar a CIMA (AEMPS)
      </button>
    </div>
    <div id="biblio-results"></div>'''

HTML_NEW = '''      <button onclick="searchBiblioLive()"
              style="padding:10px 20px;border-radius:6px;border:1px solid #1F4B4C;background:white;color:#1F4B4C;cursor:pointer;font-size:14px;">
        Cercar en viu a PubMed
      </button>
    </div>
    <div id="biblio-results"></div>'''

# ---------------------------------------------------------------
# PARCHE 2: fusionar searchBiblio() para que incluya CIMA
# ---------------------------------------------------------------

JS_OLD = '''    function renderBiblioResults(results, resultsDiv, live) {
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
    }'''

JS_NEW = '''    function articleCardsHtml(results, live) {
      if (!results || !results.length) return '';
      const badge = live
        ? '<span style="background:#fef3c7;color:#92400e;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">EN VIU · SENSE VERIFICAR</span>'
        : '<span style="background:#dcfce7;color:#166534;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">VERIFICAT</span>';
      return results.map((r, i) => `
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

    function aempsCardHtml(r) {
      if (!r) return '';
      return `
        <div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:10px;">
          <strong>${r.nombre || ''}</strong>
          <span style="background:#dcfce7;color:#166534;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">VERIFICAT · CIMA AEMPS</span>
          <br><span style="color:#666;font-size:13px;">${r.laboratorio || ''} — nº registre ${r.nregistro || '-'}</span>
          <p style="font-size:14px;margin-top:8px;"><strong>Contraindicacions:</strong> ${r.contraindicaciones || 'no disponible'}</p>
          <p style="font-size:14px;"><strong>Interaccions:</strong> ${r.interacciones || 'no disponible'}</p>
          <p style="font-size:14px;"><strong>Reaccions adverses:</strong> ${r.reacciones_adversas || 'no disponible'}</p>
        </div>
      `;
    }

    function renderBiblioResults(results, resultsDiv, live) {
      currentBiblioResults = results || [];
      const html = articleCardsHtml(results, live);
      resultsDiv.innerHTML = html || '<p>Sense resultats.</p>';
    }'''

JS_SEARCHBIBLIO_OLD = '''    async function searchBiblio() {
      const q = document.getElementById('biblio-query').value.trim();
      const resultsDiv = document.getElementById('biblio-results');
      if (!q) return;
      resultsDiv.innerHTML = '<p>Cercant a la base verificada...</p>';
      try {
        const resp = await fetch('/api/bibliography-search?query=' + encodeURIComponent(q) + '&limit=5');
        const data = await resp.json();
        renderBiblioResults(data.results, resultsDiv, false);
      } catch (e) {
        resultsDiv.innerHTML = '<p>Error consultant la bibliografia.</p>';
      }
    }'''

JS_SEARCHBIBLIO_NEW = '''    async function searchBiblio() {
      const q = document.getElementById('biblio-query').value.trim();
      const resultsDiv = document.getElementById('biblio-results');
      if (!q) return;
      resultsDiv.innerHTML = '<p>Cercant a la base verificada (bibliografia + CIMA)...</p>';
      try {
        const [biblioResp, aempsResp] = await Promise.all([
          fetch('/api/bibliography-search?query=' + encodeURIComponent(q) + '&limit=5'),
          fetch('/api/aemps-search?query=' + encodeURIComponent(q)),
        ]);
        const biblioData = await biblioResp.json();
        const aempsData = await aempsResp.json();

        currentBiblioResults = biblioData.results || [];
        const html = aempsCardHtml(aempsData.result) + articleCardsHtml(currentBiblioResults, false);
        resultsDiv.innerHTML = html || '<p>Sense resultats a la base verificada (bibliografia ni CIMA).</p>';
      } catch (e) {
        resultsDiv.innerHTML = '<p>Error consultant la base verificada.</p>';
      }
    }'''


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
        print("Uso: python3 merge_cima_into_verified_search.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    apply_patch(path, HTML_OLD, HTML_NEW, "boton eliminado")
    apply_patch(path, JS_OLD, JS_NEW, "funciones de render (articleCardsHtml, aempsCardHtml)")
    apply_patch(path, JS_SEARCHBIBLIO_OLD, JS_SEARCHBIBLIO_NEW, "searchBiblio (fusion con CIMA)")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
