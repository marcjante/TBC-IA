"""
TBC-AI - scripts/evaluate.py

Evaluacion estructurada del sistema contra el banco de preguntas existente
(faq_progress.json: 200 preguntas por categoria clinica via /api/chat;
faq_bank_progress.json: 360 preguntas coloquiales via /api/patient-chat).

A diferencia de generate_faq.py y generate_faq_bank.py (que solo guardan
el texto de la respuesta final), este script registra por cada pregunta:
timestamp, endpoint, modelo, top_k, distancia del fragmento mas cercano,
si se detecto palabra clave, y la clasificacion automatica.

IMPORTANTE (ver README.md, seccion "Estado de validacion"):
La clasificacion "con_respuesta / sin_cobertura" es automatica (se basa en
si el texto de la respuesta coincide con el mensaje fijo de ausencia de
informacion). NO implica verificacion clinica humana de que cada respuesta
sea correcta. Este script mide funcionamiento y trazabilidad del sistema,
no calidad clinica.

Uso:
    python3 scripts/evaluate.py                 # evalua los dos bancos
    python3 scripts/evaluate.py --bank faq       # solo faq_progress.json
    python3 scripts/evaluate.py --bank patient   # solo faq_bank_progress.json
"""

import requests
import json
import os
import sys
import argparse
from datetime import datetime

API_URL = "http://127.0.0.1:8000"
NO_INFO_MARKER = "No encuentro esta informaci"


def extract_questions(progress_file, categoria_key="categoria", pregunta_keys=("pregunta", "question")):
    """Lee un archivo de progreso existente y extrae (categoria, pregunta)
    para cada entrada, sin asumir a ciegas el nombre exacto de la clave de
    la pregunta (por si difiere entre faq_progress.json y faq_bank_progress.json)."""
    if not os.path.exists(progress_file):
        print(f"AVISO: no se encontro {progress_file}, se omite ese banco.")
        return []

    with open(progress_file, encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for _, entry in data.items():
        if not isinstance(entry, dict):
            continue
        categoria = entry.get(categoria_key, "sin_categoria")
        pregunta = None
        for k in pregunta_keys:
            if k in entry:
                pregunta = entry[k]
                break
        if pregunta is None:
            print(f"AVISO: entrada sin clave de pregunta reconocida en {progress_file}: {list(entry.keys())}")
            continue
        items.append({"categoria": categoria, "pregunta": pregunta})
    return items


def call_endpoint(endpoint, message, lang="es"):
    payload = {"message": message, "debug": True}
    if endpoint == "/api/patient-chat":
        payload["lang"] = lang
    resp = requests.post(f"{API_URL}{endpoint}", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def evaluate_bank(items, endpoint, bank_name, output_path):
    results = []
    total = len(items)
    for i, item in enumerate(items, 1):
        pregunta = item["pregunta"]
        categoria = item["categoria"]
        print(f"[{bank_name} {i}/{total}] {pregunta}")

        record = {
            "timestamp": datetime.now().isoformat(),
            "bank": bank_name,
            "endpoint": endpoint,
            "categoria": categoria,
            "pregunta": pregunta,
        }

        try:
            data = call_endpoint(endpoint, pregunta)
            response_text = data.get("response", "")
            debug_info = data.get("debug_info", {})

            record["response"] = response_text
            record["sources"] = data.get("sources", [])
            record["model"] = debug_info.get("model")
            record["top_k"] = debug_info.get("top_k")
            record["top1_distance"] = debug_info.get("top1_distance")
            record["has_keyword"] = debug_info.get("has_keyword")
            record["fragments_retrieved"] = debug_info.get("fragments_retrieved")
            # Clasificacion automatica -- ver aviso en la cabecera del script.
            record["classification_auto"] = (
                "sin_cobertura" if response_text.strip().startswith(NO_INFO_MARKER) else "con_respuesta"
            )
            record["error"] = None
        except Exception as e:
            record["response"] = None
            record["error"] = str(e)
            record["classification_auto"] = "error"

        results.append(record)

        # Guardado incremental: si se interrumpe, no se pierde el progreso.
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    return results


def summarize(results, bank_name):
    con_respuesta = sum(1 for r in results if r["classification_auto"] == "con_respuesta")
    sin_cobertura = sum(1 for r in results if r["classification_auto"] == "sin_cobertura")
    errores = sum(1 for r in results if r["classification_auto"] == "error")
    total = len(results)
    print(f"\n--- Resumen {bank_name} ---")
    print(f"Total: {total} | Con respuesta: {con_respuesta} | Sin cobertura: {sin_cobertura} | Errores: {errores}")
    return {"total": total, "con_respuesta": con_respuesta, "sin_cobertura": sin_cobertura, "errores": errores}


def main():
    parser = argparse.ArgumentParser(description="Evaluacion estructurada de TBC-AI")
    parser.add_argument("--bank", choices=["faq", "patient", "both"], default="both")
    args = parser.parse_args()

    try:
        health = requests.get(f"{API_URL}/api/health", timeout=10).json()
    except Exception as e:
        print(f"ERROR: no se pudo conectar al backend en {API_URL}. ¿Esta corriendo uvicorn? Detalle: {e}")
        sys.exit(1)

    print(f"Backend activo. Modelo: {health.get('model')}. Documentos indexados: {health.get('documentos_indexados')}\n")

    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    all_summaries = {}

    if args.bank in ("faq", "both"):
        faq_items = extract_questions("faq_progress.json")
        if faq_items:
            out_path = f"evaluation_faq_{run_timestamp}.json"
            results = evaluate_bank(faq_items, "/api/chat", "faq_200", out_path)
            all_summaries["faq_200"] = summarize(results, "faq_200")
            print(f"Guardado: {out_path}")

    if args.bank in ("patient", "both"):
        patient_items = extract_questions("faq_bank_progress.json")
        if patient_items:
            out_path = f"evaluation_patient_bank_{run_timestamp}.json"
            results = evaluate_bank(patient_items, "/api/patient-chat", "banco_360", out_path)
            all_summaries["banco_360"] = summarize(results, "banco_360")
            print(f"Guardado: {out_path}")

    summary_path = f"evaluation_summary_{run_timestamp}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": run_timestamp,
            "model": health.get("model"),
            "documentos_indexados": health.get("documentos_indexados"),
            "banks": all_summaries,
            "nota": "Clasificacion automatica (texto de respuesta vs. mensaje fijo de ausencia de informacion). No implica verificacion clinica humana.",
        }, f, ensure_ascii=False, indent=2)

    print(f"\nResumen global guardado en: {summary_path}")


if __name__ == "__main__":
    main()
