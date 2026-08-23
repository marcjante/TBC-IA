#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade un tercer boton "Cercar a CIMA (AEMPS)" al buscador ya existente en
la pagina principal, junto a "Cercar (base verificada)" y "Cercar en viu
a PubMed". Consulta la ficha tecnica oficial de medicamentos autorizados
en España (CIMA, AEMPS): contraindicaciones, interacciones, reacciones
adversas.

Aplica dos parches:
  1. backend/rag.py  -> añade las funciones de CIMA al final
  2. backend/main.py -> extiende el import, añade el tercer boton, la
     funcion JS searchAemps(), y el endpoint /api/aemps-search

Uso:
    python3 add_aemps_search.py "/ruta/a/backend/rag.py" "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# PARCHE 1: backend/rag.py
# ---------------------------------------------------------------

RAG_ANCHOR = '''    try:
        resp = requests.get(
            f"{BIBLIOGRAPHY_API_URL}/v1/bibliography",
            params={"query": query_text, "limit": limit},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []'''

RAG_ADDITION = '''    try:
        resp = requests.get(
            f"{BIBLIOGRAPHY_API_URL}/v1/bibliography",
            params={"query": query_text, "limit": limit},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []


# ==============================================================================
# CIMA / AEMPS — ficha tecnica oficial de medicamentos autorizados en España
# ==============================================================================
# A diferencia de PubMed (investigacion) o las guias OMS/CDC/ECDC
# (recomendaciones internacionales), CIMA da la ficha tecnica OFICIAL
# vigente en España: posologia, contraindicaciones, interacciones,
# reacciones adversas. Documentacion: https://cima.aemps.es/cima/rest/

CIMA_BASE = "https://cima.aemps.es/cima/rest"
CIMA_SECCION_CONTRAINDICACIONES = "4.3"
CIMA_SECCION_INTERACCIONES = "4.5"
CIMA_SECCION_REACCIONES_ADVERSAS = "4.8"


def cima_search_medication(name, limit=10, timeout=10):
    """Busca medicamentos en CIMA por nombre (comercial o principio
    activo). Fail-open: lista vacia si falla."""
    try:
        resp = requests.get(
            f"{CIMA_BASE}/medicamentos",
            params={"nombre": name, "pagina": 1},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        resultados = data.get("resultados", [])[:limit]
        return [{
            "nregistro": r.get("nregistro"),
            "nombre": r.get("nombre"),
            "laboratorio": r.get("labtitular"),
            "comercializado": r.get("comerc"),
        } for r in resultados]
    except (requests.RequestException, ValueError, KeyError):
        return []


def cima_get_ficha_tecnica_section(nregistro, seccion, timeout=10):
    """Contenido (HTML) de una seccion concreta de la ficha tecnica
    oficial (tipo=1). Fail-open: None si falla."""
    try:
        resp = requests.get(
            f"{CIMA_BASE}/docSegmentado/contenido/1",
            params={"nregistro": nregistro, "seccion": seccion},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("contenido")
    except (requests.RequestException, ValueError, KeyError):
        return None


def _cima_strip_html(html_text):
    import re
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    return re.sub(r"\\s+", " ", text).strip()


def get_drug_safety_info(drug_name, timeout=10):
    """Busca el medicamento en CIMA (prioriza el comercializado) y
    devuelve sus secciones de seguridad ya en texto plano: contraindicaciones,
    interacciones, reacciones adversas. Fail-open: None si no se
    encuentra o falla."""
    candidatos = cima_search_medication(drug_name, timeout=timeout)
    comercializados = [c for c in candidatos if c.get("comercializado")]
    elegido = comercializados[0] if comercializados else (candidatos[0] if candidatos else None)
    if elegido is None:
        return None

    nregistro = elegido["nregistro"]
    contraindicaciones = cima_get_ficha_tecnica_section(nregistro, CIMA_SECCION_CONTRAINDICACIONES, timeout=timeout)
    interacciones = cima_get_ficha_tecnica_section(nregistro, CIMA_SECCION_INTERACCIONES, timeout=timeout)
    reacciones_adversas = cima_get_ficha_tecnica_section(nregistro, CIMA_SECCION_REACCIONES_ADVERSAS, timeout=timeout)

    return {
        "nregistro": nregistro,
        "nombre": elegido["nombre"],
        "laboratorio": elegido.get("laboratorio"),
        "contraindicaciones": _cima_strip_html(contraindicaciones),
        "interacciones": _cima_strip_html(interacciones),
        "reacciones_adversas": _cima_strip_html(reacciones_adversas),
    }'''


# ---------------------------------------------------------------
# PARCHE 2: backend/main.py
# ---------------------------------------------------------------

MAIN_IMPORT_OLD = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response, query_master_bibliography, search_pubmed_live"
MAIN_IMPORT_NEW = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response, query_master_bibliography, search_pubmed_live, get_drug_safety_info"

MAIN_HTML_OLD = '''      <button onclick="searchBiblioLive()"
              style="padding:10px 20px;border-radius:6px;border:1px solid #1F4B4C;background:white;color:#1F4B4C;cursor:pointer;font-size:14px;">
        Cercar en viu a PubMed
      </button>
    </div>
    <div id="biblio-results"></div>'''

MAIN_HTML_NEW = '''      <button onclick="searchBiblioLive()"
              style="padding:10px 20px;border-radius:6px;border:1px solid #1F4B4C;background:white;color:#1F4B4C;cursor:pointer;font-size:14px;">
        Cercar en viu a PubMed
      </button>
      <button onclick="searchAemps()"
              style="padding:10px 20px;border-radius:6px;border:1px solid #3730a3;background:white;color:#3730a3;cursor:pointer;font-size:14px;">
        Cercar a CIMA (AEMPS)
      </button>
    </div>
    <div id="biblio-results"></div>'''

MAIN_JS_OLD = '''    async function searchBiblioLive() {
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

MAIN_JS_NEW = '''    async function searchBiblioLive() {
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
    }

    async function searchAemps() {
      const q = document.getElementById('biblio-query').value.trim();
      const resultsDiv = document.getElementById('biblio-results');
      if (!q) return;
      resultsDiv.innerHTML = '<p>Cercant a CIMA (AEMPS)...</p>';
      try {
        const resp = await fetch('/api/aemps-search?query=' + encodeURIComponent(q));
        const data = await resp.json();
        if (!data.result) {
          resultsDiv.innerHTML = '<p>No shan trobat medicaments amb aquest nom a CIMA.</p>';
          return;
        }
        const r = data.result;
        resultsDiv.innerHTML = `
          <div style="border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:10px;">
            <strong>${r.nombre || ''}</strong>
            <span style="background:#e0e7ff;color:#3730a3;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">CIMA · FITXA OFICIAL AEMPS</span>
            <br><span style="color:#666;font-size:13px;">${r.laboratorio || ''} — nº registre ${r.nregistro || '-'}</span>
            <p style="font-size:14px;margin-top:8px;"><strong>Contraindicacions:</strong> ${r.contraindicaciones || 'no disponible'}</p>
            <p style="font-size:14px;"><strong>Interaccions:</strong> ${r.interacciones || 'no disponible'}</p>
            <p style="font-size:14px;"><strong>Reaccions adverses:</strong> ${r.reacciones_adversas || 'no disponible'}</p>
          </div>
        `;
      } catch (e) {
        resultsDiv.innerHTML = '<p>Error consultant CIMA.</p>';
      }
    }'''

MAIN_ENDPOINT_OLD = '''@app.get("/api/translate")
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

MAIN_ENDPOINT_NEW = '''@app.get("/api/translate")
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
        return {"translated": None, "error": True}


@app.get("/api/aemps-search")
def aemps_search(query: str):
    """Busca un medicamento en CIMA (AEMPS) y devuelve su ficha tecnica
    oficial: contraindicaciones, interacciones, reacciones adversas.
    Fail-open: result=None si no se encuentra o falla la consulta."""
    try:
        result = get_drug_safety_info(query)
    except Exception:
        result = None
    return {"query": query, "result": result}'''


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
        print("Uso: python3 add_aemps_search.py <ruta a backend/rag.py> <ruta a backend/main.py>")
        sys.exit(1)

    rag_path, main_path = sys.argv[1], sys.argv[2]

    print(f"Parcheando {rag_path}...")
    apply_patch(rag_path, RAG_ANCHOR, RAG_ADDITION, "rag.py (funciones de CIMA)")

    print(f"Parcheando {main_path}...")
    apply_patch(main_path, MAIN_IMPORT_OLD, MAIN_IMPORT_NEW, "main.py (import)")
    apply_patch(main_path, MAIN_HTML_OLD, MAIN_HTML_NEW, "main.py (boton nuevo)")
    apply_patch(main_path, MAIN_JS_OLD, MAIN_JS_NEW, "main.py (javascript)")
    apply_patch(main_path, MAIN_ENDPOINT_OLD, MAIN_ENDPOINT_NEW, "main.py (endpoint nuevo)")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
