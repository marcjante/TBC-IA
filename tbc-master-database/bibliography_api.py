#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio pequeño e independiente que expone tbc_master.db (la base
bibliografica verificada, ver build_tbc_master_database.py) como una API
consultable, en su propio puerto (8002), igual que tbc-ia-sota-engine (8000)
es un servicio aparte que TBC-AI (8001) consulta.

Esto permite que TBC-AI o el motor complementario pidan bibliografia
verificada (PubMed + Europe PMC, confirmada por PubTator3, validada por
CrossRef, con estado de retraccion) sin tener que cargar ellos mismos la
base de datos ni conocer su formato interno.

Uso:
    cd ~/Desktop/"TBC IA"/tbc-master-database
    source venv/bin/activate
    pip install fastapi uvicorn
    python3 bibliography_api.py
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from build_tbc_master_database import query_master_bibliography

DB_PATH = os.environ.get("TBC_MASTER_DB_PATH", "tbc_master.db")

app = FastAPI(title="TBC Master Bibliography API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class BibliographyResponse(BaseModel):
    query: str
    results: list


@app.get("/v1/bibliography")
def get_bibliography(query: str, limit: int = 5):
    """Busca en la base bibliografica verificada por texto libre.

    Ejemplo: GET /v1/bibliography?query=isoniazid%20resistance&limit=3
    """
    if not os.path.exists(DB_PATH):
        return BibliographyResponse(query=query, results=[])

    results = query_master_bibliography(query, db_path=DB_PATH, limit=limit)
    # Filtramos por defecto los articulos retractados: no tiene sentido
    # devolverlos como evidencia salvo que se pida explicitamente.
    results = [r for r in results if r.get("retraction_status") == "ninguna"]
    return BibliographyResponse(query=query, results=results)


@app.get("/health")
def health():
    return {"status": "ok", "db_exists": os.path.exists(DB_PATH)}


if __name__ == "__main__":
    import uvicorn
    print(f"Sirviendo bibliografia desde: {os.path.abspath(DB_PATH)}")
    uvicorn.run(app, host="127.0.0.1", port=8002)
