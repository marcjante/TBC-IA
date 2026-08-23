#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carga faq_bank_progress.json (banco real de preguntas TBC-IA) en la base
de datos SQLite del motor, sustituyendo los datos mock (DOC1/DOC2).

No usa sqlite3 en bruto sobre las tablas para evitar cargar
sentence-transformers/torch (que main.py carga al importarse). Requiere
solo la librería estándar.

Uso:
    1. Copia faq_bank_progress.json a la carpeta data/ de este proyecto.
    2. Ejecuta `python app/main.py` una vez para que se creen las tablas
       (Ctrl+C para pararlo en cuanto veas "Uvicorn running").
    3. Ejecuta: python scripts/seed_faq.py
    4. Vuelve a arrancar `python app/main.py` — cargará estos datos reales
       en vez de los de ejemplo.
"""

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "tbc_knowledge_repository/data/tbc_clinical_v7.db"
FAQ_PATH_DEFAULT = "data/faq_bank_progress.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=FAQ_PATH_DEFAULT)
    args = parser.parse_args()
    faq_path = args.input

    if not os.path.exists(DB_PATH):
        print(
            f"No existe la base de datos en {DB_PATH}.\n"
            "Ejecuta primero 'python app/main.py' al menos una vez (para que "
            "se creen las tablas), detenlo con Ctrl+C en cuanto veas "
            "'Uvicorn running', y vuelve a correr este script."
        )
        sys.exit(1)

    if not os.path.exists(faq_path):
        print(f"No encuentro {faq_path}.")
        sys.exit(1)

    with open(faq_path, encoding="utf-8") as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Elimina datos previos (mock DOC1/DOC2 u otra carga anterior de este script)
    cur.execute("DELETE FROM chunks")
    cur.execute("DELETE FROM documents")
    conn.commit()

    categorias = {}
    for entry in data.values():
        cat = entry.get("categoria", "Sin categoría")
        categorias.setdefault(cat, []).append(entry)

    doc_idx = 0
    chunk_idx = 0
    for cat, entries in categorias.items():
        doc_idx += 1
        doc_id = f"FAQCAT-{doc_idx:03d}"

        # doi/pmid se dejan NULL deliberadamente: este banco no tiene
        # identificadores bibliográficos propios, y no se inventan.
        cur.execute(
            """
            INSERT INTO documents (
                id, doi, pmid, title, authors, year, journal, evidence_level,
                topics, populations, drugs, citation_count, openalex_concepts,
                rag_priority, rag_score, retrieval_status
            ) VALUES (?, NULL, NULL, ?, ?, 2026, ?, ?, ?, ?, '', 0, ?, ?, ?, 'ACTIVE')
            """,
            (
                doc_id,
                cat,
                "Equipo clínico TBC-IA",
                "TBC-IA Knowledge Base (institucional)",
                "Institutional FAQ",
                cat,
                "patient",
                cat,
                "MEDIUM",
                0.65,
            ),
        )

        for entry in entries:
            chunk_idx += 1
            chunk_id = f"FAQCHK-{chunk_idx:04d}"
            pregunta = entry.get("pregunta", "").strip()
            respuesta = entry.get("respuesta", "").strip()
            content = f"P: {pregunta}\nR: {respuesta}"
            cur.execute(
                """
                INSERT INTO chunks (id, document_id, content, section_weight, is_guideline)
                VALUES (?, ?, ?, 1.0, 0)
                """,
                (chunk_id, doc_id, content),
            )

    conn.commit()
    conn.close()
    print(f"Cargados {doc_idx} documentos (categorías) y {chunk_idx} chunks (preguntas) desde {faq_path}.")


if __name__ == "__main__":
    main()
