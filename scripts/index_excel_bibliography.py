"""
TBC-AI - scripts/index_excel_bibliography.py

Indexa la biblioteca ampliada de referencias bibliograficas verificadas
(TBC_corpus_REAL_253_DOI_verificados.xlsx, hoja Corpus_REAL_253) en la
misma coleccion Chroma que el resto del sistema.

IMPORTANTE - naturaleza de este contenido:
Estas entradas son CITAS BIBLIOGRAFICAS BREVES (titulo, autores, resumen
de un par de frases, utilidad clinica anotada), NO el texto completo de
cada articulo. El sistema podra citar que existe evidencia sobre un tema
y de que fuente proviene, pero no tiene acceso al contenido detallado del
articulo en si (a diferencia de los PDF de OMS/CDC/ECDC, que si estan
indexados con su texto completo).

Verificacion previa (sesion de agosto 2026): se comprobaron manualmente 8
referencias de esta hoja mediante busqueda externa. Las 8 correspondian a
articulos reales (DOIs y PMIDs verificados en PubMed/editoriales), con
una unica discrepancia menor detectada: un digito incorrecto en un DOI
(TB251, corregido a mano en esta ejecucion, ver CORRECCIONES_DOI abajo).
No se ha verificado el 100% de las 253 filas una por una.

Se excluyen 11 filas que corresponden a guias OMS/ECDC ya indexadas como
PDF completo en documents/TB_full/ (evitar contenido redundante y de
menor calidad que el PDF original).

Uso:
    python3 scripts/index_excel_bibliography.py --source /ruta/al/TBC_corpus_REAL_253_DOI_verificados.xlsx
"""

import os
import sys
import argparse
import hashlib

import pandas as pd
import chromadb
import ollama

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "vector_db")
COLLECTION_NAME = "tbc_docs"
EMBED_MODEL = os.environ.get("TBC_EMBED_MODEL", "bge-m3")
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 300
MIN_ALNUM_CHARS = 40
NEW_CATEGORY = "07_Biblioteca_Ampliada_253"
SHEET_NAME = "Corpus_REAL_253"

# IDs que corresponden a guias institucionales (OMS/ECDC) ya indexadas como
# PDF completo en otro sitio del sistema. Se excluyen para no duplicar
# contenido de peor calidad (cita breve) sobre contenido ya disponible en
# texto completo.
EXCLUDE_IDS = {
    "TB001", "TB002", "TB003", "TB004", "TB005", "TB006",
    "TB007", "TB008", "TB009", "TB010", "TB012",
}

# Correcciones manuales de errores puntuales detectados durante la
# verificacion (ver docstring). Formato: {ID: DOI_correcto}
CORRECCIONES_DOI = {
    "TB251": "10.1016/j.chest.2023.08.021",
}


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        alnum_count = sum(1 for c in chunk if c.isalnum())
        if alnum_count >= MIN_ALNUM_CHARS:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def as_text(value):
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def build_document_text(row):
    titulo = as_text(row["Título"])
    autores = as_text(row["Autores/Organismo"])
    anio = as_text(row["Año"])
    revista = as_text(row["Revista/Fuente"])
    tipo_doc = as_text(row["Tipo de documento"])
    area = as_text(row["Área"])
    subtema = as_text(row["Subtema"])
    resumen = as_text(row["Resumen"])
    utilidad = as_text(row["Utilidad para RAG"])

    doi_original = as_text(row["DOI"])
    doi = CORRECCIONES_DOI.get(row["ID"], doi_original)
    pmid = as_text(row["PMID"])
    url = as_text(row["URL oficial"])
    # Si se corrigio el DOI a mano, la URL "oficial" de la hoja probablemente
    # apunte todavia al DOI incorrecto (heredado del mismo error). Se
    # reconstruye la URL a partir del DOI ya corregido en ese caso, en vez
    # de arrastrar la URL original potencialmente equivocada.
    if row["ID"] in CORRECCIONES_DOI:
        url = f"https://doi.org/{doi}"

    citas = []
    if doi and doi not in ("NO VERIFICABLE", "No verificado", "nan"):
        citas.append(f"DOI: {doi}")
    if pmid and pmid not in ("No aplica", "No verificado", "nan"):
        citas.append(f"PMID: {pmid}")
    if url and url != "nan":
        citas.append(url)
    cita_linea = " | ".join(citas) if citas else "Sin identificador digital disponible"

    text = (
        f"Referencia bibliografica ({area} / {subtema}): {titulo}\n"
        f"Autores/Organismo: {autores} ({anio})\n"
        f"Fuente: {revista} | Tipo: {tipo_doc}\n"
        f"Resumen: {resumen}\n"
        f"Utilidad clinica anotada: {utilidad}\n"
        f"Identificadores: {cita_linea}\n"
        f"\n"
        f"NOTA: esta es una cita bibliografica breve (titulo, autores, resumen),\n"
        f"no el texto completo del articulo original."
    )
    return text


def deterministic_id(row_id, chunk_index):
    h = hashlib.sha1(f"excel253_{row_id}::{chunk_index}".encode("utf-8")).hexdigest()[:16]
    return f"biblio253_{h}"


def main():
    parser = argparse.ArgumentParser(description="Indexa la biblioteca ampliada de 253 referencias")
    parser.add_argument("--source", required=True, help="Ruta al archivo TBC_corpus_REAL_253_DOI_verificados.xlsx")
    args = parser.parse_args()

    if not os.path.isfile(args.source):
        print(f"ERROR: no existe el archivo {args.source}")
        sys.exit(1)

    df = pd.read_excel(args.source, sheet_name=SHEET_NAME)
    print(f"Filas totales en la hoja {SHEET_NAME}: {len(df)}")

    df = df[~df["ID"].isin(EXCLUDE_IDS)]
    print(f"Filas tras excluir {len(EXCLUDE_IDS)} guias institucionales ya indexadas como PDF: {len(df)}")

    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    total_chunks = 0
    for _, row in df.iterrows():
        row_id = row["ID"]
        full_text = build_document_text(row)
        chunks = chunk_text(full_text)

        if not chunks:
            print(f"AVISO: {row_id} no genero ningun fragmento valido (muy corto), se omite.")
            continue

        ids = [deterministic_id(row_id, i) for i in range(len(chunks))]
        metadatas = [
            {"source": f"{row_id}: {as_text(row['Título'])[:80]}", "category": NEW_CATEGORY, "page": 0}
            for _ in chunks
        ]

        embeddings = []
        for chunk in chunks:
            emb = ollama.embeddings(model=EMBED_MODEL, prompt=chunk)["embedding"]
            embeddings.append(emb)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )
        total_chunks += len(chunks)
        print(f"Indexado: {row_id} ({len(chunks)} fragmento(s))")

    print(f"\nCompletado. Total fragmentos indexados/actualizados: {total_chunks}")
    print(f"Total documentos en la coleccion tras esta operacion: {collection.count()}")


if __name__ == "__main__":
    main()
