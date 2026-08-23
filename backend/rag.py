"""
TBC-AI - backend/rag.py

Todo lo relacionado con la recuperacion de informacion (Retrieval-Augmented
Generation):
- chunk_text() / chunk_id(): fragmentacion de texto para indexar.
- index_single_pdf(): indexacion de un PDF individual (usado por /api/upload
  y por scripts/index_documents.py de forma equivalente).
- retrieve(): consulta a ChromaDB, devuelve fragmentos/metadatos/distancias.
- is_relevant(): aplica el filtro de doble umbral (estricto/permisivo).
- query_sota_fallback(): consulta el motor tbc-ia-sota-engine cuando
  ChromaDB no encuentra nada suficientemente relevante (agosto 2026).

FASE 7 de la auditoria: extraido de main.py. Los dos endpoints de chat
(/api/chat y /api/patient-chat) llamaban a una version casi identica de
esta logica cada uno por su lado; aqui queda unificada en un solo sitio.
Los umbrales (480/750) NO se han cambiado respecto al original.
"""

import hashlib
import fitz
import ollama
import requests

from backend.config import (
    EMBED_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, MIN_ALNUM_CHARS, collection,
    SOTA_ENGINE_URL, SOTA_ENGINE_API_KEY,
)

STRICT_DISTANCE_THRESHOLD = 480
LOOSE_DISTANCE_THRESHOLD = 750


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            alnum_count = sum(1 for c in chunk if c.isalnum())
            if alnum_count >= MIN_ALNUM_CHARS:
                chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def chunk_id(source_file, page_num, chunk_index):
    raw = f"{source_file}|{page_num}|{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def index_single_pdf(pdf_path, category, fname):
    doc = fitz.open(pdf_path)
    total_chunks = 0

    for i, page in enumerate(doc):
        page_num = i + 1
        text = page.get_text().strip()
        if not text:
            continue

        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            cid = chunk_id(f"{category}/{fname}", page_num, idx)
            embedding = ollama.embeddings(model=EMBED_MODEL, prompt=chunk)["embedding"]

            collection.upsert(
                ids=[cid],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "source": fname,
                    "category": category,
                    "page": page_num,
                }],
            )
            total_chunks += 1

    doc.close()
    return total_chunks


def retrieve(query_text, top_k):
    """Genera el embedding de la pregunta (con el prefijo fijo 'Tuberculosis: '
    que mejora la recuperacion en preguntas cortas) y consulta la coleccion.
    Devuelve (fragments, metadatas, distances), cada uno una lista, vacias
    si no hay resultados."""
    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + query_text)["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []
    return fragments, metadatas, distances


_bm25_index = None
_bm25_ids = None
_bm25_docs = None
_bm25_metas = None


def _build_bm25_index():
    """Construye el indice BM25 sobre TODO el corpus de ChromaDB (no solo
    los top_k de una consulta). Se llama una sola vez, la primera vez que
    se necesita, y se cachea en variables de modulo."""
    global _bm25_index, _bm25_ids, _bm25_docs, _bm25_metas
    import re
    from rank_bm25 import BM25Okapi

    all_data = collection.get(include=["documents", "metadatas"])
    _bm25_ids = all_data["ids"]
    _bm25_docs = all_data["documents"]
    _bm25_metas = all_data["metadatas"]

    tokenized_corpus = [re.findall(r"\w+", (doc or "").lower()) for doc in _bm25_docs]
    _bm25_index = BM25Okapi(tokenized_corpus)


def _get_bm25_index():
    if _bm25_index is None:
        _build_bm25_index()
    return _bm25_index, _bm25_ids, _bm25_docs, _bm25_metas


def hybrid_retrieve(query_text, top_k):
    """Recuperacion hibrida: BM25 + ChromaDB denso, fusionados con
    Reciprocal Rank Fusion (RRF). Pensada para sustituir a retrieve()
    como motor PRINCIPAL (Fase 2 de la propuesta de arquitectura TBC-AI
    v2, agosto 2026) — antes BM25 solo entraba via el motor
    complementario, y unicamente cuando ChromaDB por si solo no era
    relevante.

    Devuelve (fragments, metadatas, distances) en el MISMO formato que
    retrieve(), para poder sustituirla sin cambiar el resto del codigo.
    Fail-open: si BM25 falla por cualquier motivo, se usa solo el
    resultado denso de ChromaDB (el comportamiento de retrieve() de
    siempre), nunca rompe la recuperacion."""
    import re
    import numpy as np

    fetch_k = max(top_k * 3, 30)

    # --- Denso (ChromaDB), consulta directa para tener acceso a los ids ---
    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + query_text)["embedding"]
    dense_results = collection.query(query_embeddings=[query_embedding], n_results=fetch_k)
    dense_ids = dense_results["ids"][0] if dense_results["ids"] else []
    dense_docs = dense_results["documents"][0] if dense_results["documents"] else []
    dense_metas = dense_results["metadatas"][0] if dense_results["metadatas"] else []
    dense_distances = dense_results["distances"][0] if dense_results["distances"] else []

    if not dense_ids:
        return [], [], []

    dense_lookup = {
        doc_id: (doc, meta, dist)
        for doc_id, doc, meta, dist in zip(dense_ids, dense_docs, dense_metas, dense_distances)
    }

    # --- BM25 sobre el mismo corpus completo (indice cacheado) ---
    try:
        bm25_index, bm25_ids, bm25_docs, bm25_metas = _get_bm25_index()
        tokenized_query = re.findall(r"\w+", query_text.lower())
        bm25_scores = bm25_index.get_scores(tokenized_query)
        bm25_top_local = np.argsort(bm25_scores)[::-1][:fetch_k]
        bm25_ranked_ids = [bm25_ids[i] for i in bm25_top_local]
        bm25_lookup = {bm25_ids[i]: (bm25_docs[i], bm25_metas[i]) for i in bm25_top_local}
    except Exception as e:
        print(f"[DEBUG hybrid_retrieve] BM25 fallo, usando solo denso: {type(e).__name__}: {e}")
        bm25_ranked_ids = []
        bm25_lookup = {}

    # --- Fusion RRF por id ---
    k_rrf = 60
    rrf_scores = {}
    for rank, doc_id in enumerate(dense_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)
    for rank, doc_id in enumerate(bm25_ranked_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank + 1)

    fused_ids = [doc_id for doc_id, _ in sorted(rrf_scores.items(), key=lambda x: -x[1])][:top_k]

    # Reconstruir en el orden fusionado. Si el id viene de la busqueda
    # densa, usamos su distancia real. Si solo aparece via BM25 (no
    # estaba entre los top de ChromaDB), no hay distancia de embeddings
    # real disponible: usamos como valor centinela el umbral estricto,
    # ni lo descarta ni lo prioriza artificialmente en is_relevant().
    fragments, metadatas, distances = [], [], []
    for doc_id in fused_ids:
        if doc_id in dense_lookup:
            doc, meta, dist = dense_lookup[doc_id]
        elif doc_id in bm25_lookup:
            doc, meta = bm25_lookup[doc_id]
            dist = STRICT_DISTANCE_THRESHOLD
        else:
            continue
        fragments.append(doc)
        metadatas.append(meta)
        distances.append(dist)

    return fragments, metadatas, distances


def is_relevant(fragments, distances, has_keyword):
    """Aplica el filtro de doble umbral: si la pregunta contiene una palabra
    clave relacionada con tuberculosis, se usa el umbral permisivo (750);
    si no, el estricto (480). Devuelve False si no hay fragmentos o si la
    distancia del mejor resultado supera el umbral aplicable."""
    if not fragments or not distances:
        return False
    threshold = LOOSE_DISTANCE_THRESHOLD if has_keyword else STRICT_DISTANCE_THRESHOLD
    return distances[0] <= threshold


def query_sota_fallback(query_text, timeout=8):
    """Consulta el motor tbc-ia-sota-engine (recuperacion hibrida BM25+denso
    con reranking, servido aparte en http://127.0.0.1:8000) cuando ChromaDB
    no ha encontrado nada suficientemente relevante (is_relevant() == False).

    Devuelve una tupla (fragments, metadatas, info):
    - Si el motor detecta una alerta clinica (ej. toxicidad ocular por
      etambutol), info = {"alert": [...]} y fragments/metadatas van vacios:
      quien llama debe mostrar la alerta, no generar una respuesta libre.
    - Si hay evidencia con confianza suficiente (no LOW/INSUFFICIENT),
      devuelve fragments/metadatas en el mismo formato que retrieve(), e
      info = {"confidence": "...", "source": "sota_engine"}.
    - Si el motor no responde, falla, o no hay evidencia util, devuelve
      ([], [], None) para que quien llama use el mensaje de "sin cobertura"
      habitual sin romper el flujo.

    No lanza excepciones hacia arriba: cualquier fallo de red o de formato
    se trata como "sin evidencia adicional", nunca como error 500 para el
    usuario final.
    """
    try:
        resp = requests.post(
            f"{SOTA_ENGINE_URL}/v1/evidence",
            params={"query": query_text},
            headers={"X-API-Key": SOTA_ENGINE_API_KEY},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return [], [], None

    if data.get("alerts"):
        return [], [], {"alert": data["alerts"]}

    confidence = data.get("confidence_level")
    evidence = data.get("grounded_evidence", [])
    if not evidence or confidence in (None, "INSUFFICIENT", "LOW"):
        return [], [], None

    fragments = [e.get("content", "") for e in evidence]
    metadatas = [
        {
            "source": "TBC-IA Knowledge Base (motor de recuperación complementario)",
            "category": e.get("document_id", ""),
            "page": None,
        }
        for e in evidence
    ]
    return fragments, metadatas, {"confidence": confidence, "source": "sota_engine"}


def verify_groundedness(response_text, sources, timeout=15):
    """Consulta /v1/verify_groundedness en el motor complementario para
    detectar frases de una respuesta ya generada que no estan respaldadas
    por ninguna fuente (fabricacion silenciosa del LLM, sin frase de aviso
    reconocible por LEAK_PATTERNS/REFUSAL_PATTERNS en safety.py).

    NO decide nada sobre la respuesta: solo informa. Devuelve None si el
    motor no responde o falla (fail-open: nunca bloquea el flujo normal
    por un problema de este chequeo adicional, que todavia esta sin
    calibrar contra casos reales — ver aviso en tbc-ia-sota-engine/app/main.py).
    """
    if not sources:
        return None
    try:
        resp = requests.post(
            f"{SOTA_ENGINE_URL}/v1/verify_groundedness",
            json={"response_text": response_text, "sources": sources},
            headers={"X-API-Key": SOTA_ENGINE_API_KEY},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


LLAMAFILE_URL = "http://127.0.0.1:8081"


def query_llamafile_response(context_text, question, timeout=90):
    """Genera una respuesta independiente con un segundo modelo (Mistral 7B
    via Llamafile, servido aparte en http://127.0.0.1:8081) para la misma
    pregunta y el mismo contexto que uso Ollama. Es la mitad "B" del
    consenso entre dos modelos (señal secundaria, ver compare_with_llamafile
    en main.py) - probado hoy como prototipo en dual_model_check.py.

    Fail-open: devuelve None si el servidor no responde, esta caido, o el
    formato de respuesta no es el esperado. Nunca lanza excepcion, para no
    romper el flujo normal de /api/chat si Llamafile no esta corriendo."""
    # Recorte del contexto para Llamafile especificamente (no afecta al
    # contexto completo usado por Llama 3.1 para la respuesta principal).
    # Hallazgo del 23 de agosto de 2026: tras hybrid_retrieve() (mas
    # fuentes por pregunta), Llamafile empezo a fallar por timeout de
    # forma consistente con contextos grandes — no estaba colgado,
    # simplemente tardaba mas de 90s en procesarlos en este hardware.
    MAX_LLAMAFILE_CONTEXT_CHARS = 6000
    if len(context_text) > MAX_LLAMAFILE_CONTEXT_CHARS:
        context_text = context_text[:MAX_LLAMAFILE_CONTEXT_CHARS] + "\n\n[...contexto recortado para el segundo modelo...]"

    system_prompt = (
        "Eres un asistente clinico. Responde la pregunta del paciente "
        "usando exclusivamente el CONTEXTO proporcionado. No inventes "
        "informacion que no este en el contexto."
    )
    user_prompt = f"CONTEXTO:\n{context_text}\n\nPREGUNTA:\n{question}"
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    try:
        resp = requests.post(f"{LLAMAFILE_URL}/v1/chat/completions", json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        print(f"[DEBUG query_llamafile_response] Fallo: {type(e).__name__}: {e}")
        return None


def search_pubmed_live(query_text, max_results=5, timeout=15):
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
    """Busca medicamentos en CIMA. El parametro "nombre" de la API de CIMA
    busca SOLO por nombre comercial (ej. "Rimactan"), no por principio
    activo (ej. "rifampicina") — confirmado con pruebas reales. Por eso
    se prueba primero por principio activo (practiv1, el caso mas
    habitual: alguien escribe el nombre generico del farmaco), y solo si
    no hay resultados se prueba por nombre comercial.

    Fail-open: lista vacia si falla."""
    def _parse(data):
        # IMPORTANTE: no recortar aqui a "limit" — CIMA devuelve sus
        # resultados ordenados alfabeticamente por marca comercial, asi
        # que recortar antes de priorizar por nombre dejaria fuera los
        # genericos "PARACETAMOL X" si empiezan por una letra mas
        # avanzada que las marcas comerciales (ej. "ACTRON", "ANTIDOL").
        # Se recorta al final, despues de reordenar por prioridad.
        return [{
            "nregistro": r.get("nregistro"),
            "nombre": r.get("nombre"),
            "laboratorio": r.get("labtitular"),
            "comercializado": r.get("comerc"),
        } for r in data.get("resultados", [])]

    def _prioritize_name_match(resultados, term):
        """Pone primero los medicamentos cuyo nombre comercial contiene
        literalmente el termino buscado (suelen ser el generico "puro"),
        por delante de marcas que no lo mencionan (a menudo combinados
        con otros principios activos, ej. "ACTRON" para "paracetamol")."""
        term_lower = term.lower()
        con_nombre = [r for r in resultados if term_lower in (r.get("nombre") or "").lower()]
        sin_nombre = [r for r in resultados if term_lower not in (r.get("nombre") or "").lower()]
        return con_nombre + sin_nombre

    try:
        resp = requests.get(
            f"{CIMA_BASE}/medicamentos",
            params={"practiv1": name, "pagina": 1},
            timeout=timeout,
        )
        resp.raise_for_status()
        resultados = _parse(resp.json())
        if resultados:
            return _prioritize_name_match(resultados, name)[:limit]

        # Sin resultados por principio activo: probar por nombre comercial
        resp2 = requests.get(
            f"{CIMA_BASE}/medicamentos",
            params={"nombre": name, "pagina": 1},
            timeout=timeout,
        )
        resp2.raise_for_status()
        return _parse(resp2.json())[:limit]
    except (requests.RequestException, ValueError, KeyError):
        return []


def cima_get_ficha_tecnica_section(nregistro, seccion, timeout=10):
    """Contenido de una seccion concreta de la ficha tecnica oficial
    (tipo=1). CIMA devuelve este endpoint en DOS formatos distintos segun
    la seccion — confirmado con pruebas reales: algunas secciones dan
    texto plano directo (Content-Type: text/plain), otras dan una LISTA
    JSON de objetos con una clave "contenido" (con entidades HTML
    numericas dentro, ej. &#193; en vez de "Á"). Esta funcion detecta
    cual de los dos formatos llego y lo normaliza a texto.

    Fail-open: None si falla o el medicamento no tiene esa seccion."""
    import json as json_module

    try:
        resp = requests.get(
            f"{CIMA_BASE}/docSegmentado/contenido/1",
            params={"nregistro": nregistro, "seccion": seccion},
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.text.strip()
        if not text:
            return None

        # Formato JSON (lista de objetos con "contenido"). CIMA devuelve
        # a veces JSON tecnicamente invalido (saltos de linea sin escapar
        # dentro de las cadenas) — confirmado con pruebas reales, de ahi
        # strict=False para tolerarlo.
        if text.startswith("["):
            try:
                data = json_module.loads(text, strict=False)
                if isinstance(data, list) and data:
                    return data[0].get("contenido")
            except (ValueError, KeyError, IndexError, AttributeError):
                pass

        # Formato texto plano directo
        return text
    except requests.RequestException:
        return None


def _cima_strip_html(html_text):
    """Quita etiquetas HTML y decodifica entidades HTML numericas
    (&#193; -> Á), necesario porque algunas secciones de CIMA (ver
    cima_get_ficha_tecnica_section) devuelven el contenido asi codificado."""
    import re
    import html as html_module
    if not html_text:
        return ""
    text = html_module.unescape(html_text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
    }
