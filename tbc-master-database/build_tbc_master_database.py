#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TBC Master Database — pipeline independiente que combina PubMed y Europe PMC,
filtra y verifica con PubTator3, deduplica, valida con CrossRef, comprueba
retracciones/erratas (con los propios metadatos de PubMed, sin servicio
adicional), y guarda todo en una base de datos SQLite separada
(tbc_master.db), pensada para conectarse mas adelante con tbc-ia-sota-engine
como fuente de bibliografia verificada.

IMPORTANTE — PubTator3 no es una tercera fuente de articulos independiente:
es una capa de anotaciones de entidades (enfermedad/farmaco/relacion) sobre
los MISMOS articulos de PubMed/PMC. Aqui se usa para VERIFICAR que un
articulo realmente trata de tuberculosis (no solo que la palabra aparece) y
para extraer que farmacos/quimicos menciona, no para descubrir articulos
nuevos.

Uso:
    cd ~/Desktop/"TBC IA"/tbc-ia-sota-engine   (o donde prefieras instalarlo)
    source venv/bin/activate
    pip install biopython requests
    python3 build_tbc_master_database.py --query "tuberculosis treatment" --max-results 100

Requiere (recomendado, aunque no obligatorio) un email de contacto para
NCBI E-utilities y, opcionalmente, una API key de NCBI para mas throughput:
    export NCBI_EMAIL="tu_email@ejemplo.com"
    export NCBI_API_KEY="tu_api_key"   # opcional
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata

import requests

NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "anonymous@example.com")
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", None)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PUBTATOR_EXPORT_BASE = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson"
CROSSREF_BASE = "https://api.crossref.org/works"

# Identificador MeSH de tuberculosis, para verificar con PubTator3 que la
# anotacion de enfermedad realmente corresponde a tuberculosis (no solo que
# la palabra aparece en el texto).
TB_MESH_ID = "MESH:D014376"

# Farmacos de interes para marcar que quimicos/farmacos aparecen en cada
# articulo (ampliable segun necesites).
DRUGS_OF_INTEREST = [
    "isoniazid", "rifampicin", "rifampin", "pyrazinamide", "ethambutol",
    "bedaquiline", "delamanid", "pretomanid", "linezolid", "clofazimine",
    "moxifloxacin", "levofloxacin", "streptomycin", "amikacin",
    "cycloserine", "rifapentine",
]

# Temas generales para el modo --auto-queries (ademas de una consulta por
# cada farmaco de la lista de arriba)
GENERAL_TOPICS = [
    "tuberculosis treatment guidelines",
    "tuberculosis diagnosis",
    "latent tuberculosis infection",
    "multidrug resistant tuberculosis",
    "tuberculosis pediatric",
    "tuberculosis pregnancy",
    "tuberculosis adverse effects",
    "tuberculosis adherence",
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ==============================================================================
# 1. HARVEST: PubMed (via E-utilities)
# ==============================================================================

def fetch_pubmed(query, max_results=200, batch_size=100):
    """Busca en PubMed y devuelve una lista de diccionarios con los campos
    principales, incluida la deteccion de retracciones/erratas a partir de
    CommentsCorrectionsList (gratis, ya viene en los propios metadatos)."""
    import xml.etree.ElementTree as ET

    log(f"PubMed: buscando '{query}' (maximo {max_results})...")
    params = {
        "db": "pubmed", "term": query, "retmax": max_results,
        "retmode": "json", "email": NCBI_EMAIL,
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    resp = requests.get(f"{EUTILS_BASE}/esearch.fcgi", params=params, timeout=30)
    resp.raise_for_status()
    pmids = resp.json().get("esearchresult", {}).get("idlist", [])
    log(f"PubMed: {len(pmids)} PMIDs encontrados.")

    records = []
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        fetch_params = {
            "db": "pubmed", "id": ",".join(batch), "retmode": "xml",
            "email": NCBI_EMAIL,
        }
        if NCBI_API_KEY:
            fetch_params["api_key"] = NCBI_API_KEY
        r = requests.get(f"{EUTILS_BASE}/efetch.fcgi", params=fetch_params, timeout=60)
        r.raise_for_status()
        root = ET.fromstring(r.content)

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
            if year_el is None:
                year_el = article.find(".//PubDate/MedlineDate")
            year = None
            if year_el is not None and year_el.text:
                match = re.search(r"\d{4}", year_el.text)
                year = int(match.group()) if match else None

            journal_el = article.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else None

            authors = []
            for author in article.findall(".//AuthorList/Author"):
                last = author.find("LastName")
                fore = author.find("ForeName")
                if last is not None:
                    name = last.text
                    if fore is not None:
                        name = f"{last.text} {fore.text}"
                    authors.append(name)

            pub_types = [
                pt.text for pt in article.findall(".//PublicationTypeList/PublicationType")
            ]
            mesh_terms = [
                mh.find("DescriptorName").text
                for mh in article.findall(".//MeshHeadingList/MeshHeading")
                if mh.find("DescriptorName") is not None
            ]

            doi = None
            for id_el in article.findall(".//ArticleIdList/ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text

            pmcid = None
            for id_el in article.findall(".//ArticleIdList/ArticleId"):
                if id_el.get("IdType") == "pmc":
                    pmcid = id_el.text

            # Retracciones / erratas: gratis, en los propios metadatos de PubMed
            retraction_status = "ninguna"
            for cc in article.findall(".//CommentsCorrectionsList/CommentsCorrections"):
                ref_type = cc.get("RefType", "")
                if ref_type == "RetractionIn":
                    retraction_status = "retractado"
                elif ref_type == "ErratumIn" and retraction_status == "ninguna":
                    retraction_status = "errata"
                elif ref_type == "UpdateIn" and retraction_status == "ninguna":
                    retraction_status = "actualizado"

            records.append({
                "pmid": pmid, "pmcid": pmcid, "doi": doi, "title": title,
                "abstract": abstract, "authors": authors, "year": year,
                "journal": journal, "pub_types": pub_types, "mesh_terms": mesh_terms,
                "source": "pubmed", "retraction_status": retraction_status,
            })
        time.sleep(0.34)  # limite de 3 peticiones/segundo sin API key

    log(f"PubMed: {len(records)} registros completos descargados.")
    return records


# ==============================================================================
# 2. HARVEST: Europe PMC
# ==============================================================================

def fetch_europepmc(query, max_results=200, page_size=100):
    log(f"Europe PMC: buscando '{query}' (maximo {max_results})...")
    records = []
    cursor_mark = "*"
    while len(records) < max_results:
        params = {
            "query": query, "format": "json", "pageSize": min(page_size, max_results - len(records)),
            "cursorMark": cursor_mark,
        }
        resp = requests.get(EUROPEPMC_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("resultList", {}).get("result", [])
        if not results:
            break
        for r in results:
            records.append({
                "pmid": r.get("pmid"), "pmcid": r.get("pmcid"), "doi": r.get("doi"),
                "title": r.get("title", ""), "abstract": r.get("abstractText", ""),
                "authors": [a.strip() for a in (r.get("authorString") or "").split(",") if a.strip()],
                "year": int(r["pubYear"]) if r.get("pubYear") else None,
                "journal": r.get("journalTitle"), "pub_types": r.get("pubType", "").split("; ") if r.get("pubType") else [],
                "mesh_terms": [], "source": "europepmc", "retraction_status": "ninguna",
            })
        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor_mark:
            break
        cursor_mark = next_cursor
        time.sleep(0.2)

    log(f"Europe PMC: {len(records)} registros descargados.")
    return records


# ==============================================================================
# 3. DEDUPLICACION
# ==============================================================================

def normalize_title(title):
    title = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    title = re.sub(r"[^\w\s]", "", title.lower())
    return re.sub(r"\s+", " ", title).strip()


def deduplicate(records):
    log(f"Deduplicando {len(records)} registros...")
    by_key = {}
    order = []
    for rec in records:
        key = None
        if rec.get("doi"):
            key = ("doi", rec["doi"].strip().lower())
        elif rec.get("pmid"):
            key = ("pmid", rec["pmid"])
        else:
            key = ("title", normalize_title(rec.get("title", "")))

        if key in by_key:
            existing = by_key[key]
            # Combinar fuentes y rellenar campos que falten
            sources = set(existing["source"].split("+")) | {rec["source"]}
            existing["source"] = "+".join(sorted(sources))
            for field in ("pmid", "pmcid", "doi", "abstract", "journal", "year"):
                if not existing.get(field) and rec.get(field):
                    existing[field] = rec[field]
            if len(rec.get("mesh_terms", [])) > len(existing.get("mesh_terms", [])):
                existing["mesh_terms"] = rec["mesh_terms"]
        else:
            by_key[key] = dict(rec)
            order.append(key)

    result = [by_key[k] for k in order]
    log(f"Deduplicacion: {len(records)} -> {len(result)} registros unicos.")
    return result


# ==============================================================================
# 4. VERIFICACION CON PUBTATOR3 (entidades: enfermedad + farmacos)
# ==============================================================================

def pubtator_verify(records, batch_size=100):
    log("Verificando con PubTator3 (anotaciones de entidades)...")
    pmid_to_record = {r["pmid"]: r for r in records if r.get("pmid")}
    pmids = list(pmid_to_record.keys())

    for rec in records:
        rec["pubtator_verified"] = False
        rec["pubtator_drugs"] = []

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        try:
            resp = requests.get(
                PUBTATOR_EXPORT_BASE,
                params={"pmids": ",".join(batch)},
                timeout=60,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            log(f"  AVISO: fallo PubTator3 en este lote ({type(e).__name__}: {e}), se omite.")
            continue

        # El endpoint devuelve BioC-JSON: una lista de "documents", cada uno
        # con "passages", cada passage con "annotations" (entidades).
        try:
            data = resp.json()
            documents = data if isinstance(data, list) else data.get("PubTator3", data.get("documents", []))
        except (ValueError, json.JSONDecodeError):
            log("  AVISO: respuesta de PubTator3 no interpretable como JSON, se omite este lote.")
            continue

        for doc in documents:
            pmid = str(doc.get("pmid") or doc.get("id") or "")
            if pmid not in pmid_to_record:
                continue
            rec = pmid_to_record[pmid]
            found_tb = False
            found_drugs = set()
            for passage in doc.get("passages", []):
                for ann in passage.get("annotations", []):
                    infons = ann.get("infons", {})
                    identifier = infons.get("identifier", "")
                    entity_type = infons.get("type", "")
                    text = ann.get("text", "").lower()
                    if identifier == TB_MESH_ID or "tuberculosis" in text:
                        if entity_type.lower() == "disease":
                            found_tb = True
                    if entity_type.lower() == "chemical":
                        for drug in DRUGS_OF_INTEREST:
                            if drug in text:
                                found_drugs.add(drug)
            rec["pubtator_verified"] = found_tb
            rec["pubtator_drugs"] = sorted(found_drugs)

        time.sleep(0.34)

    verified_count = sum(1 for r in records if r.get("pubtator_verified"))
    log(f"PubTator3: {verified_count}/{len(records)} articulos con tuberculosis confirmada como entidad.")
    return records


# ==============================================================================
# 5. VALIDACION CON CROSSREF
# ==============================================================================

def crossref_validate(records):
    log("Validando DOIs con CrossRef...")
    validated = 0
    for rec in records:
        rec["crossref_validated"] = False
        doi = rec.get("doi")
        if not doi:
            continue
        try:
            resp = requests.get(f"{CROSSREF_BASE}/{doi}", timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("message", {})
                crossref_title = " ".join(data.get("title", []))
                rec["crossref_validated"] = True
                rec["crossref_title"] = crossref_title
                validated += 1
        except requests.RequestException:
            pass
        time.sleep(0.05)

    log(f"CrossRef: {validated} DOIs validados de {sum(1 for r in records if r.get('doi'))} con DOI.")
    return records


# ==============================================================================
# 6. ALMACENAMIENTO EN SQLITE
# ==============================================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmid TEXT UNIQUE,
    pmcid TEXT,
    doi TEXT,
    title TEXT,
    abstract TEXT,
    authors TEXT,
    year INTEGER,
    journal TEXT,
    pub_types TEXT,
    mesh_terms TEXT,
    source TEXT,
    retraction_status TEXT,
    pubtator_verified INTEGER,
    pubtator_drugs TEXT,
    crossref_validated INTEGER,
    crossref_title TEXT,
    date_added TEXT
);
"""


def store_to_sqlite(records, db_path="tbc_master.db"):
    log(f"Guardando {len(records)} registros en {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    for rec in records:
        conn.execute(
            """INSERT INTO articles
               (pmid, pmcid, doi, title, abstract, authors, year, journal,
                pub_types, mesh_terms, source, retraction_status,
                pubtator_verified, pubtator_drugs, crossref_validated,
                crossref_title, date_added)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(pmid) DO UPDATE SET
                 pmcid=excluded.pmcid, doi=excluded.doi, title=excluded.title,
                 abstract=excluded.abstract, source=excluded.source,
                 retraction_status=excluded.retraction_status,
                 pubtator_verified=excluded.pubtator_verified,
                 pubtator_drugs=excluded.pubtator_drugs,
                 crossref_validated=excluded.crossref_validated,
                 crossref_title=excluded.crossref_title""",
            (
                rec.get("pmid"), rec.get("pmcid"), rec.get("doi"), rec.get("title"),
                rec.get("abstract"), json.dumps(rec.get("authors", []), ensure_ascii=False),
                rec.get("year"), rec.get("journal"),
                json.dumps(rec.get("pub_types", []), ensure_ascii=False),
                json.dumps(rec.get("mesh_terms", []), ensure_ascii=False),
                rec.get("source"), rec.get("retraction_status", "ninguna"),
                int(rec.get("pubtator_verified", False)),
                json.dumps(rec.get("pubtator_drugs", []), ensure_ascii=False),
                int(rec.get("crossref_validated", False)),
                rec.get("crossref_title"), now,
            ),
        )
    conn.commit()

    retracted = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE retraction_status != 'ninguna'"
    ).fetchone()[0]

    # Reconstruir el indice de busqueda rapida (FTS5) sobre titulo+abstract.
    # Se reconstruye entero cada vez (la base es de miles de filas, no
    # millones, así que es barato) para no tener que sincronizar triggers.
    conn.execute("DROP TABLE IF EXISTS articles_fts")
    conn.execute(
        "CREATE VIRTUAL TABLE articles_fts USING fts5("
        "pmid UNINDEXED, title, abstract, content='articles', content_rowid='id')"
    )
    conn.execute(
        "INSERT INTO articles_fts(rowid, pmid, title, abstract) "
        "SELECT id, pmid, title, abstract FROM articles"
    )
    conn.commit()
    conn.close()
    log(f"Guardado completo. {retracted} articulos marcados con retraccion/errata/actualizacion.")
    log("Indice de busqueda rapida (FTS5) reconstruido.")


def query_master_bibliography(query_text, db_path="tbc_master.db", limit=5):
    """Busca en la base maestra por texto libre (titulo+abstract), usando el
    indice FTS5. Devuelve una lista de diccionarios con los campos
    principales, ordenados por relevancia. Pensado para que lo use
    tbc-ia-sota-engine como fuente adicional de bibliografia verificada."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # FTS5 usa su propia sintaxis de consulta; escapamos comillas dobles y
    # unimos las palabras con OR para tolerar consultas de varias palabras.
    safe_terms = " OR ".join(
        f'"{term}"' for term in re.findall(r"\w+", query_text) if len(term) > 2
    )
    if not safe_terms:
        conn.close()
        return []

    rows = conn.execute(
        """SELECT a.pmid, a.doi, a.title, a.abstract, a.year, a.journal,
                  a.pubtator_verified, a.pubtator_drugs, a.retraction_status
           FROM articles_fts f
           JOIN articles a ON a.id = f.rowid
           WHERE articles_fts MATCH ?
           ORDER BY rank
           LIMIT ?""",
        (safe_terms, limit),
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "pmid": row["pmid"], "doi": row["doi"], "title": row["title"],
            "abstract": row["abstract"], "year": row["year"], "journal": row["journal"],
            "pubtator_verified": bool(row["pubtator_verified"]),
            "pubtator_drugs": json.loads(row["pubtator_drugs"] or "[]"),
            "retraction_status": row["retraction_status"],
        })
    return results


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", help="Consulta de busqueda (repetible: --query a --query b)")
    parser.add_argument("--auto-queries", action="store_true",
                         help="Genera automaticamente una consulta por cada farmaco de DRUGS_OF_INTEREST "
                              "mas los temas generales de GENERAL_TOPICS")
    parser.add_argument("--max-results", type=int, default=100, help="Maximo de resultados por fuente y consulta")
    parser.add_argument("--db", default="tbc_master.db", help="Ruta de la base de datos SQLite")
    parser.add_argument("--skip-pubtator", action="store_true", help="Omitir verificacion con PubTator3")
    parser.add_argument("--skip-crossref", action="store_true", help="Omitir validacion con CrossRef")
    args = parser.parse_args()

    if args.auto_queries:
        queries = [f"tuberculosis {drug}" for drug in DRUGS_OF_INTEREST] + GENERAL_TOPICS
    elif args.query:
        queries = args.query
    else:
        queries = ["tuberculosis treatment"]

    log(f"Se van a ejecutar {len(queries)} consulta(s): {queries if len(queries) <= 5 else queries[:5] + ['...']}")

    total_pubmed = total_europepmc = 0
    all_records = []
    for i, query in enumerate(queries, start=1):
        log(f"\n--- Consulta {i}/{len(queries)}: '{query}' ---")
        pubmed_records = fetch_pubmed(query, max_results=args.max_results)
        europepmc_records = fetch_europepmc(query, max_results=args.max_results)
        total_pubmed += len(pubmed_records)
        total_europepmc += len(europepmc_records)
        all_records.extend(pubmed_records)
        all_records.extend(europepmc_records)

    unique_records = deduplicate(all_records)

    if not args.skip_pubtator:
        unique_records = pubtator_verify(unique_records)
    if not args.skip_crossref:
        unique_records = crossref_validate(unique_records)

    store_to_sqlite(unique_records, db_path=args.db)

    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"Consultas ejecutadas: {len(queries)}")
    print(f"PubMed (total bruto): {total_pubmed}")
    print(f"Europe PMC (total bruto): {total_europepmc}")
    print(f"Tras deduplicar:     {len(unique_records)}")
    if not args.skip_pubtator:
        print(f"Verificados (TB):    {sum(1 for r in unique_records if r.get('pubtator_verified'))}")
    if not args.skip_crossref:
        print(f"Validados (DOI):     {sum(1 for r in unique_records if r.get('crossref_validated'))}")
    retracted = sum(1 for r in unique_records if r.get("retraction_status") != "ninguna")
    print(f"Retractados/erratas: {retracted}")
    print(f"\nBase de datos: {args.db}")


if __name__ == "__main__":
    main()
