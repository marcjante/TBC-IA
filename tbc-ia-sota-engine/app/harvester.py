#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Harvester real multi-fuente: PubMed, Europe PMC, Crossref, OpenAlex.

Deliberadamente NO importa app/main.py (evita cargar sentence-transformers/
torch solo para insertar filas en SQLite). Solo depende de `requests`
(ya está en requirements.txt).

IMPORTANTE: este código no se ha podido ejecutar ni probar contra las APIs
reales en este entorno (sandbox sin acceso de red a pubmed/crossref/europepmc).
Está escrito según la documentación pública de cada API, pero pruébalo con
una consulta pequeña antes de confiar en él para cargas grandes.

Uso como script:
    python app/harvester.py "tuberculosis pediatric isoniazid dosing" --limit 10

Esto busca en PubMed, resuelve DOI/citas vía OpenAlex cuando existe DOI,
e inserta los documentos encontrados en la base de datos (sin chunks —
los chunks de texto real habría que extraerlos del abstract o del PDF
correspondiente; aquí solo se guarda el abstract como chunk único).
"""

import argparse
import os
import re
import sqlite3
import sys
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DB_PATH = "tbc_knowledge_repository/data/tbc_clinical_v7.db"

NCBI_EMAIL = os.getenv("NCBI_EMAIL", "tbc_ia_research@domain.org")
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")

session = requests.Session()
retries = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

EVIDENCE_WEIGHTS = {
    "Clinical guideline": 1.0,
    "Meta-analysis": 0.95,
    "Systematic review": 0.90,
    "Randomized controlled trial": 0.85,
    "Clinical trial": 0.75,
    "Cohort study": 0.70,
    "Narrative review": 0.60,
}


def compute_rag_score(evidence_level: str, year: int, citations: int):
    score = EVIDENCE_WEIGHTS.get(evidence_level, 0.40)
    if year and year >= datetime.now().year - 5:
        score += 0.05
    if citations > 500:
        score += 0.08
    elif citations > 100:
        score += 0.04
    elif citations > 20:
        score += 0.02
    score = min(1.0, score)
    prio = "HIGH" if score >= 0.80 else ("MEDIUM" if score >= 0.60 else "LOW")
    return prio, round(score, 3)


def guess_evidence_level(title: str, pub_types: list, abstract: str = "") -> str:
    """Heurística a partir de PublicationType de PubMed, combinado siempre
    con palabras clave en título/abstract (PubMed suele devolver solo
    "Journal Article" en publicaciones muy recientes aún no indexadas del
    todo, así que no basta con mirar pub_types cuando no está vacío).
    No inventa nivel de evidencia si no hay pistas: por defecto 'Narrative
    review'."""
    combined = f"{' '.join(pub_types)} {title} {abstract}".lower()

    if "guideline" in combined:
        return "Clinical guideline"
    if "meta-analysis" in combined or "meta analysis" in combined:
        return "Meta-analysis"
    if "systematic review" in combined:
        return "Systematic review"
    if re.search(r"randomi[sz]ed", combined) and "trial" in combined:
        return "Randomized controlled trial"
    if re.search(r"\brct\b", combined):
        return "Randomized controlled trial"
    if "clinical trial" in combined:
        return "Clinical trial"
    if "cohort study" in combined or "cohort" in combined:
        return "Cohort study"
    return "Narrative review"


# ==============================================================================
# PUBMED (NCBI E-utilities)
# ==============================================================================

def search_pubmed(query: str, retmax: int = 20) -> list:
    """Devuelve una lista de PMIDs para la query dada."""
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": retmax,
        "email": NCBI_EMAIL,
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    r = session.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def fetch_pubmed_summaries(pmids: list) -> list:
    """Metadatos básicos (título, autores, año, revista, DOI si está)."""
    if not pmids:
        return []
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
        "email": NCBI_EMAIL,
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    r = session.get(url, params=params, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    docs = []
    for pmid in result.get("uids", []):
        item = result.get(pmid, {})
        doi = ""
        for aid in item.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
        year = 0
        pubdate = item.get("pubdate", "")
        if pubdate[:4].isdigit():
            year = int(pubdate[:4])
        docs.append({
            "pmid": pmid,
            "doi": doi,
            "title": item.get("title", "").strip(),
            "authors": ", ".join(a.get("name", "") for a in item.get("authors", [])),
            "year": year,
            "journal": item.get("fulljournalname", "") or item.get("source", ""),
            "pub_types": item.get("pubtype", []),
        })
    return docs


def fetch_pubmed_abstract(pmid: str) -> str:
    """Abstract en texto plano vía efetch (formato rettype=abstract)."""
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": pmid,
        "rettype": "abstract",
        "retmode": "text",
        "email": NCBI_EMAIL,
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    r = session.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.text.strip()


# ==============================================================================
# EUROPE PMC (alternativa/complemento a PubMed, cubre preprints y más fuentes)
# ==============================================================================

def search_europepmc(query: str, page_size: int = 20) -> list:
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {"query": query, "format": "json", "pageSize": page_size}
    r = session.get(url, params=params, timeout=15)
    r.raise_for_status()
    results = r.json().get("resultList", {}).get("result", [])
    docs = []
    for item in results:
        docs.append({
            "pmid": item.get("pmid", ""),
            "doi": item.get("doi", ""),
            "title": item.get("title", ""),
            "authors": item.get("authorString", ""),
            "year": int(item.get("pubYear", 0)) if item.get("pubYear", "").isdigit() else 0,
            "journal": item.get("journalTitle", ""),
            "pub_types": [item.get("pubType", "")] if item.get("pubType") else [],
        })
    return docs


# ==============================================================================
# CROSSREF (metadatos por DOI, útil cuando PubMed no da todos los campos)
# ==============================================================================

def fetch_crossref_by_doi(doi: str) -> dict:
    if not doi:
        return {}
    url = f"https://api.crossref.org/works/{doi}"
    try:
        r = session.get(url, headers={"User-Agent": f"mailto:{NCBI_EMAIL}"}, timeout=15)
        if r.status_code == 200:
            return r.json().get("message", {})
    except requests.RequestException:
        pass
    return {}


# ==============================================================================
# OPENALEX (métricas de impacto — mismo endpoint que en main.py)
# ==============================================================================

def fetch_openalex_metrics(doi: str) -> dict:
    if not doi:
        return {"cited_by_count": 0, "concepts": ""}
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    try:
        r = session.get(url, headers={"User-Agent": f"mailto:{NCBI_EMAIL}"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            concepts = [c["display_name"] for c in data.get("concepts", []) if c.get("score", 0) > 0.6]
            return {"cited_by_count": data.get("cited_by_count", 0), "concepts": "; ".join(concepts)}
    except requests.RequestException:
        pass
    return {"cited_by_count": 0, "concepts": ""}


# ==============================================================================
# INGESTA A SQLITE
# ==============================================================================

def insert_document(cur, doc: dict, topic: str, abstract: str = ""):
    doi = doc.get("doi") or None
    pmid = doc.get("pmid") or None
    year = doc.get("year") or 0
    evidence_level = guess_evidence_level(doc.get("title", ""), doc.get("pub_types", []), abstract)

    metrics = fetch_openalex_metrics(doi) if doi else {"cited_by_count": 0, "concepts": ""}
    citations = metrics["cited_by_count"]
    prio, score = compute_rag_score(evidence_level, year, citations)

    doc_id = f"PMID-{pmid}" if pmid else f"DOI-{doi}" if doi else f"NODOI-{doc.get('title', '')[:40]}"

    try:
        cur.execute(
            """
            INSERT OR IGNORE INTO documents (
                id, doi, pmid, title, authors, year, journal, evidence_level,
                topics, populations, drugs, citation_count, openalex_concepts,
                rag_priority, rag_score, retrieval_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, 'ACTIVE')
            """,
            (
                doc_id, doi, pmid, doc.get("title", ""), doc.get("authors", ""),
                year, doc.get("journal", ""), evidence_level, topic,
                citations, metrics["concepts"], prio, score,
            ),
        )
        return doc_id, cur.rowcount > 0
    except sqlite3.IntegrityError as e:
        print(f"  Aviso: no se insertó {doc_id} ({e})")
        return doc_id, False


def ingest(query: str, limit: int, source: str = "pubmed", fetch_abstracts: bool = True):
    if not os.path.exists(DB_PATH):
        print(f"No existe la base de datos en {DB_PATH}. Arranca app/main.py una vez antes de esto.")
        sys.exit(1)

    if source == "pubmed":
        pmids = search_pubmed(query, retmax=limit)
        print(f"PubMed: {len(pmids)} resultados para '{query}'")
        docs = fetch_pubmed_summaries(pmids)
    elif source == "europepmc":
        docs = search_europepmc(query, page_size=limit)
        print(f"Europe PMC: {len(docs)} resultados para '{query}'")
    else:
        raise ValueError("source debe ser 'pubmed' o 'europepmc'")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    inserted = 0
    chunk_idx = int(time.time())  # evita colisión de ids entre ejecuciones
    for doc in docs:
        abstract = ""
        if fetch_abstracts and doc.get("pmid"):
            try:
                abstract = fetch_pubmed_abstract(doc["pmid"])
            except requests.RequestException:
                abstract = ""

        doc_id, was_new = insert_document(cur, doc, topic=query, abstract=abstract)
        if was_new:
            inserted += 1
            content = abstract or doc.get("title", "")
            if content:
                chunk_idx += 1
                cur.execute(
                    """
                    INSERT INTO chunks (id, document_id, content, section_weight, is_guideline)
                    VALUES (?, ?, ?, 1.0, 0)
                    """,
                    (f"HARV-{chunk_idx}", doc_id, content),
                )
        time.sleep(0.34)  # respeta el límite de NCBI (~3 req/seg sin api_key)

    conn.commit()
    conn.close()
    print(f"Insertados {inserted} documentos nuevos de {len(docs)} encontrados.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harvester real para TBC IA SOTA Engine")
    parser.add_argument("query", help="Término de búsqueda, p. ej. 'tuberculosis pediatric isoniazid dosing'")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--source", choices=["pubmed", "europepmc"], default="pubmed")
    parser.add_argument("--no-abstracts", action="store_true", help="No descargar abstracts (solo metadatos)")
    args = parser.parse_args()

    ingest(args.query, args.limit, source=args.source, fetch_abstracts=not args.no_abstracts)
