#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integra el servicio de bibliografia verificada (tbc-master-database,
puerto 8002) en /api/chat, como fuente adicional de evidencia junto a las
fuentes clinicas (FAQ/PDF) que ya se usan.

Aplica dos parches:
  1. backend/rag.py  -> añade query_master_bibliography() al final
  2. backend/main.py -> amplia el import de backend.rag, y añade la
     llamada dentro de /api/chat, justo antes de construir context_text

Uso:
    python3 add_bibliography_integration.py "/ruta/a/backend/rag.py" "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# PARCHE 1: backend/rag.py — añadir query_master_bibliography()
# ---------------------------------------------------------------

RAG_ANCHOR = '''    try:
        resp = requests.post(f"{LLAMAFILE_URL}/v1/chat/completions", json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        print(f"[DEBUG query_llamafile_response] Fallo: {type(e).__name__}: {e}")
        return None'''

RAG_ADDITION = '''    try:
        resp = requests.post(f"{LLAMAFILE_URL}/v1/chat/completions", json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        print(f"[DEBUG query_llamafile_response] Fallo: {type(e).__name__}: {e}")
        return None


BIBLIOGRAPHY_API_URL = "http://127.0.0.1:8002"


def query_master_bibliography(query_text, limit=3, timeout=10):
    """Consulta el servicio de bibliografia verificada (tbc_master.db:
    PubMed + Europe PMC, confirmado por PubTator3, validado por CrossRef,
    con estado de retraccion — ver tbc-master-database/bibliography_api.py).

    Señal complementaria a las fuentes clinicas (FAQ/PDF) ya usadas en
    /api/chat: aporta literatura cientifica reciente cuando esta
    disponible, no las sustituye.

    Fail-open: devuelve lista vacia si el servicio no responde o falla,
    para no romper el flujo normal de /api/chat si el servicio de
    bibliografia no esta corriendo."""
    try:
        resp = requests.get(
            f"{BIBLIOGRAPHY_API_URL}/v1/bibliography",
            params={"query": query_text, "limit": limit},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []'''


# ---------------------------------------------------------------
# PARCHE 2: backend/main.py
# ---------------------------------------------------------------

MAIN_IMPORT_OLD = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response"
MAIN_IMPORT_NEW = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness, query_llamafile_response, query_master_bibliography"

MAIN_CONTEXT_ANCHOR = '''        sources_used.append({
            "source": meta["source"],
            "category": meta["category"],
            "page": meta.get("page"),
            "text": frag,
        })

    context_text = "\\n\\n---\\n\\n".join(context_parts)'''

MAIN_CONTEXT_ADDITION = '''        sources_used.append({
            "source": meta["source"],
            "category": meta["category"],
            "page": meta.get("page"),
            "text": frag,
        })

    # Bibliografia cientifica verificada adicional (PubMed + Europe PMC,
    # confirmado por PubTator3, validado por CrossRef — ver
    # tbc-master-database/). Señal complementaria: no sustituye a las
    # fuentes clinicas de arriba (FAQ/PDF), solo añade literatura reciente
    # cuando esta disponible. Fail-open: si el servicio (puerto 8002) no
    # responde, sigue funcionando igual que hasta ahora, sin ella.
    bibliography_results = query_master_bibliography(request.message, limit=2)
    for bib in bibliography_results:
        if bib.get("retraction_status") != "ninguna":
            continue
        cite = f"{bib.get('journal') or 'revista desconocida'} ({bib.get('year') or 's.f.'})"
        context_parts.append(
            f"[Fuente: bibliografia cientifica verificada, {cite}]\\n"
            f"{bib.get('title', '')}\\n{bib.get('abstract', '')}"
        )
        sources_used.append({
            "source": f"PubMed/Europe PMC - {cite}",
            "category": "bibliografia_cientifica",
            "page": None,
            "text": bib.get("abstract") or bib.get("title", ""),
            "doi": bib.get("doi"),
            "pmid": bib.get("pmid"),
        })

    context_text = "\\n\\n---\\n\\n".join(context_parts)'''


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
        print("Uso: python3 add_bibliography_integration.py <ruta a backend/rag.py> <ruta a backend/main.py>")
        sys.exit(1)

    rag_path, main_path = sys.argv[1], sys.argv[2]

    print(f"Parcheando {rag_path}...")
    apply_patch(rag_path, RAG_ANCHOR, RAG_ADDITION, "rag.py (funcion nueva)")

    print(f"Parcheando {main_path}...")
    apply_patch(main_path, MAIN_IMPORT_OLD, MAIN_IMPORT_NEW, "main.py (import)")
    apply_patch(main_path, MAIN_CONTEXT_ANCHOR, MAIN_CONTEXT_ADDITION, "main.py (bloque de contexto)")

    print("\nHecho. Reinicia los servicios para probarlo.")


if __name__ == "__main__":
    main()
