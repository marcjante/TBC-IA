# TBC IA — Clinical Evidence & Hybrid RAG Engine (v7.0)

Motor RAG híbrido para evidencia clínica sobre tuberculosis. Combina recuperación dispersa (BM25) y densa (bi-encoder), fusión RRF, reranking con CrossEncoder, detección de contradicciones (NLI) y exportación bibliográfica a formato RIS.

## Componentes

- **Harvester**: integración con OpenAlex para métricas de impacto (citas, conceptos) por DOI.
- **Retriever híbrido**: `BM25Retriever` (sparse) + `SentenceTransformer` (`BAAI/bge-small-en-v1.5`, dense), fusionados con Reciprocal Rank Fusion.
- **Reranking**: `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- **Detección de contradicciones**: `cross-encoder/nli-deberta-v3-small`.
- **Persistencia**: SQLite en modo WAL vía SQLAlchemy (`DocumentORM`, `ChunkORM`).
- **API**: FastAPI con dos endpoints (`/v1/evidence`, `/v1/admin/export/ris`), autenticación por cabecera `X-API-Key`.

## Estructura

```
tbc-ia-sota-engine/
├── app/
│   └── main.py          # API + pipeline RAG
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Instalación

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # rellenar TBC_API_KEY y NCBI_EMAIL
```

## Ejecución

```bash
python app/main.py
```

Servidor en `http://127.0.0.1:8000`. Documentación interactiva en `/docs`.

## Endpoints

### `POST /v1/evidence?query=...`
Cabecera `X-API-Key` requerida. Devuelve evidencia recuperada, nivel de confianza (`HIGH`/`MODERATE`/`LOW`/`INSUFFICIENT`) y estado de contradicción (`SUPPORTED`/`CONFLICTING`/`NO_EVIDENCE`). Si detecta patrones de alerta clínica (p. ej. toxicidad ocular por etambutol), devuelve `EMERGENCY_URGENT` sin pasar por retrieval.

### `GET /v1/admin/export/ris?topic=...`
Exporta el corpus activo a formato `.RIS` (Zotero/EndNote), con métricas de citas incluidas como notas.

## Cargar el banco de preguntas real (360 FAQ)

Sustituye los datos de ejemplo (DOC1/DOC2) por el banco real de 360 preguntas clínicas (`faq_bank_progress.json`, 10 categorías × 36 preguntas):

```bash
cp /ruta/a/faq_bank_progress.json data/faq_bank_progress.json
python app/main.py        # arranca una vez para crear las tablas; Ctrl+C al ver "Uvicorn running"
python scripts/seed_faq.py
python app/main.py        # vuelve a arrancar; ahora indexa las 360 preguntas reales
```

`scripts/seed_faq.py` no inventa DOI ni PMID para estas entradas — se dejan a `NULL` porque el banco no tiene identificadores bibliográficos propios. Cada categoría se guarda como un "documento" y cada pregunta como un chunk (`P: ... / R: ...`).

## Harvester real (PubMed / Europe PMC / OpenAlex)

`app/harvester.py` es independiente de `app/main.py` (no carga `torch`/`sentence-transformers`, solo `requests`) para poder nutrir la base de datos con literatura real sin arrancar el servidor completo:

```bash
python app/harvester.py "tuberculosis pediatric isoniazid dosing" --limit 10
python app/harvester.py "MDR-TB bedaquiline safety" --source europepmc --limit 15
```

Busca en PubMed o Europe PMC, resuelve citas de OpenAlex cuando hay DOI, calcula `rag_score`/`rag_priority` con la misma heurística que `main.py`, y guarda el abstract como chunk único por documento.

**Aviso**: este harvester no se ha podido probar contra las APIs reales en el entorno donde se escribió (sin acceso de red a NCBI/Crossref/EuropePMC). La lógica sigue la documentación pública de cada API, pero pruébalo primero con `--limit 3` antes de una carga grande, y revisa que los campos (`title`, `authors`, `doi`) se rellenan correctamente.

## Estado conocido / pendiente

- Los datos de ejemplo (`_load_mock_data_if_empty`) se cargan automáticamente si la base está vacía; sustituir por el harvester real (PubMed/Crossref/Europe PMC) cuando esté disponible.
- `NCBI_API_KEY` está declarada pero no se usa todavía en las llamadas HTTP.
