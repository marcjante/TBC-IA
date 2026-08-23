#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade busqueda en vivo directa a PubMed (via E-utilities), ademas de la
busqueda ya existente en la base verificada (tbc_master.db). Se marcan
claramente como cosas distintas: la base local esta verificada (PubTator3
+ CrossRef + deteccion de retracciones); la busqueda en vivo NO pasa por
esos filtros, es solo lo que devuelve PubMed en el momento.

Aplica dos parches:
  1. backend/rag.py  -> añade search_pubmed_live() al final
  2. backend/main.py -> añade el endpoint /api/bibliography-search-live
     y un segundo boton en la pagina principal

Uso:
    python3 add_live_pubmed_search.py "/ruta/a/backend/rag.py" "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# PARCHE 1: backend/rag.py
# ---------------------------------------------------------------

RAG_ANCHOR = '''BIBLIOGRAPHY_API_URL = "http://127.0.0.1:8002"


def query_master_bibliography(query_text, limit=3, timeout=10):'''

RAG_ADDITION = '''def search_pubmed_live(query_text, max_results=5, timeout=15):
    """Busca en vivo directamente en PubMed (E-utilities), sin pasar por
    la base verificada local. NO tiene verificacion de PubTator3, ni
    validacion de CrossRef, ni deteccion de retracciones — es solo lo que
    PubMed devuelve en el momento. Pensado para la caja de busqueda de la
    pagina principal cuando la base local no tiene lo que se busca.

    Fail-open: devuelve lista vacia si falla cualquier paso."""
    import xml.etree.ElementTree as ET

    try:
        params = {
            "db": "pubmed", "term": query_text, "retmax": max_results,
            "retmode": "json",
        }
        resp = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params=params, timeout=timeout,
        )
        resp.raise_for_status()
        pmids = resp.json().get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        fetch_resp = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
            timeout=timeout,
        )
        fetch_resp.raise_for_status()
        root = ET.fromstring(fetch_resp.content)

        results = []
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else None

            title_el = article.find(".//ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else ""

            abstract_parts = [
                "".join(a.itertext()) for a in article.findall(".//AbstractText")
            ]
            abstract = " ".join(abstract_parts)

            year_el = article.find(".//PubDate/Year")
            year = int(year_el.text) if year_el is not None and year_el.text and year_el.text.isdigit() else None

            journal_el = article.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else None

            doi = None
            for id_el in article.findall(".//ArticleIdList/ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text

            results.append({
                "pmid": pmid, "doi": doi, "title": title, "abstract": abstract,
                "year": year, "journal": journal,
            })
        return results
    except (requests.RequestException, ET.ParseError, ValueError):
        return []


BIBLIOGRAPHY_API_URL = "http://127.0.0.1:8002"


def query_master_bibliography(query_text, limit=3, timeout=10):'''


# ---------------------------------------------------------------
# PARCHE 2: backend/main.py
# ---------------------------------------------------------------

MAIN_IMPORT_OLD = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response, query_master_bibliography"
MAIN_IMPORT_NEW = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response, query_master_bibliography, search_pubmed_live"

MAIN_HTML_OLD = '''      <button onclick="searchBiblio()"
              style="padding:10px 20px;border-radius:6px;border:none;background:#1F4B4C;color:white;cursor:pointer;font-size:14px;">
        Cercar
      </button>
    </div>
    <div id="biblio-results"></div>'''

MAIN_HTML_NEW = '''      <button onclick="searchBiblio()"
              style="padding:10px 20px;border-radius:6px;border:none;background:#1F4B4C;color:white;cursor:pointer;font-size:14px;">
        Cercar (base verificada)
      </button>
      <button onclick="searchBiblioLive()"
              style="padding:10px 20px;border-radius:6px;border:1px solid #1F4B4C;background:white;color:#1F4B4C;cursor:pointer;font-size:14px;">
        Cercar en viu a PubMed
      </button>
    </div>
    <div id="biblio-results"></div>'''

MAIN_JS_OLD = '''    async function searchBiblio() {
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
    }'''

MAIN_JS_NEW = '''    function renderBiblioResults(results, resultsDiv, live) {
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
    }

    async function searchBiblio() {
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
    }

    async function searchBiblioLive() {
      const q = document.getElementById('biblio-query').value.trim();
      const resultsDiv = document.getElementById('biblio-results');
      if (!q) return;
      resultsDiv.innerHTML = '<p>Cercant en viu a PubMed (pot trigar unes segons)...</p>';
      try {
        const resp = await fetch('/api/bibliography-search-live?query=' + encodeURIComponent(q) + '&limit=5');
        const data = await resp.json();
        renderBiblioResults(data.results, resultsDiv, true);
      } catch (e) {
        resultsDiv.innerHTML = '<p>Error consultant PubMed en viu.</p>';
      }
    }'''

MAIN_ENDPOINT_OLD = '''@app.get("/api/bibliography-search")
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

MAIN_ENDPOINT_NEW = '''@app.get("/api/bibliography-search")
def bibliography_search(query: str, limit: int = 5):
    """Busca en la bibliografia verificada (tbc_master.db) directamente,
    sin pasar por el puerto 8002 (reutiliza query_master_bibliography, ya
    usada en /api/chat). Fail-open: devuelve lista vacia si falla."""
    try:
        results = query_master_bibliography(query, limit=limit)
    except Exception:
        results = []
    results = [r for r in results if r.get("retraction_status") == "ninguna"]
    return {"query": query, "results": results}


@app.get("/api/bibliography-search-live")
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
    if len(sys.argv) != 3:
        print("Uso: python3 add_live_pubmed_search.py <ruta a backend/rag.py> <ruta a backend/main.py>")
        sys.exit(1)

    rag_path, main_path = sys.argv[1], sys.argv[2]

    print(f"Parcheando {rag_path}...")
    apply_patch(rag_path, RAG_ANCHOR, RAG_ADDITION, "rag.py (funcion nueva)")

    print(f"Parcheando {main_path}...")
    apply_patch(main_path, MAIN_IMPORT_OLD, MAIN_IMPORT_NEW, "main.py (import)")
    apply_patch(main_path, MAIN_HTML_OLD, MAIN_HTML_NEW, "main.py (boton nuevo)")
    apply_patch(main_path, MAIN_JS_OLD, MAIN_JS_NEW, "main.py (javascript)")
    apply_patch(main_path, MAIN_ENDPOINT_OLD, MAIN_ENDPOINT_NEW, "main.py (endpoint nuevo)")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
