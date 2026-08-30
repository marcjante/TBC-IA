#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evaluacion sistematica del pipeline completo /api/chat con las 560
preguntas del banco. Diseñado para dejarse corriendo desatendido
durante muchas horas:

  - Guarda cada resultado INMEDIATAMENTE tras recibirlo (no al final),
    en un archivo .jsonl (una linea = un resultado) — si se corta a
    media noche, no se pierde el trabajo ya hecho.
  - Si ya existe un archivo de resultados con el mismo nombre, RETOMA
    desde donde se quedo (salta las preguntas ya respondidas), en vez
    de volver a empezar de cero.
  - Si una pregunta falla (error de red, timeout), se registra el
    fallo y se sigue con la siguiente — un fallo no detiene el resto.
  - Pensado para ejecutarse con nohup, sobreviviendo al cierre de la
    terminal (igual que el resto de servicios de este proyecto).

Uso:
    python3 evaluate_full_pipeline.py

Para dejarlo corriendo toda la noche sin que se corte al cerrar la
terminal:
    nohup python3 evaluate_full_pipeline.py > evaluation_run.log 2>&1 &
    disown
"""

import json
import time
import sys
from datetime import datetime

import requests

BANCO_PATH = "banco_560_preguntas.json"
RESULTADOS_PATH = "evaluation_results_560.jsonl"
API_URL = "http://127.0.0.1:8001/api/chat"
TIMEOUT_POR_PREGUNTA = 400  # segundos; hemos visto respuestas de hasta ~5 min


def cargar_banco():
    with open(BANCO_PATH, encoding="utf-8") as f:
        return json.load(f)


def cargar_ids_ya_hechos():
    """Lee el archivo de resultados si ya existe, para retomar desde
    donde se quedo en vez de repetir preguntas ya respondidas.

    IMPORTANTE: los resultados marcados como "error" NO cuentan como
    hechos — se reintentan automaticamente en la siguiente ejecucion,
    ya que en una tirada de muchas horas es esperable algun fallo
    pasajero (timeout puntual, reinicio del servidor) que merece la
    pena reintentar, no dejar marcado como definitivo para siempre."""
    ids_hechos = set()
    try:
        with open(RESULTADOS_PATH, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    resultado = json.loads(linea)
                    if resultado.get("clasificacion") != "error":
                        ids_hechos.add(resultado["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    except FileNotFoundError:
        pass
    return ids_hechos


def clasificar_resultado(data):
    """Clasifica el resultado en una categoria de alto nivel, para
    poder resumir facilmente despues."""
    if "error" in data:
        return "error"
    respuesta = data.get("response", "")
    coverage = data.get("coverage")
    if "no encuentro esta informacion" in respuesta.lower() or "no encuentro esta información" in respuesta.lower():
        return "no_se"
    if "urgencia" in respuesta.lower() or "112" in respuesta:
        return "urgencia_medica"
    if "024" in respuesta:
        return "riesgo_autolesion"
    if coverage:
        return f"respondida_{coverage}"
    return "respondida_sin_cobertura_marcada"


def evaluar_pregunta(item):
    """Envia una pregunta a /api/chat y devuelve el resultado completo
    con metadatos. Nunca lanza excepcion hacia arriba: cualquier fallo
    se registra como parte del resultado."""
    inicio = time.time()
    try:
        resp = requests.post(
            API_URL,
            json={
                "message": item["pregunta"],
                "history": [],
                "top_k": 8,
                "debug": True,
            },
            timeout=TIMEOUT_POR_PREGUNTA,
        )
        resp.raise_for_status()
        data = resp.json()
        duracion = time.time() - inicio
        return {
            "id": item["id"],
            "categoria": item["categoria"],
            "pregunta": item["pregunta"],
            "lang": item["lang"],
            "timestamp": datetime.now().isoformat(),
            "duracion_segundos": round(duracion, 1),
            "response": data.get("response"),
            "coverage": data.get("coverage"),
            "num_sources": len(data.get("sources", [])),
            "llm_unsupported_claims": data.get("debug_info", {}).get("llm_unsupported_claims"),
            "dual_model_agreement": data.get("debug_info", {}).get("dual_model_comparison", {}).get("agreement"),
            "clasificacion": clasificar_resultado(data),
        }
    except Exception as e:
        duracion = time.time() - inicio
        return {
            "id": item["id"],
            "categoria": item["categoria"],
            "pregunta": item["pregunta"],
            "lang": item["lang"],
            "timestamp": datetime.now().isoformat(),
            "duracion_segundos": round(duracion, 1),
            "error": f"{type(e).__name__}: {e}",
            "clasificacion": "error",
        }


def main():
    banco = cargar_banco()
    ids_ya_hechos = cargar_ids_ya_hechos()

    pendientes = [item for item in banco if item["id"] not in ids_ya_hechos]

    print(f"Banco total: {len(banco)} preguntas")
    print(f"Ya evaluadas (retomando): {len(ids_ya_hechos)}")
    print(f"Pendientes: {len(pendientes)}")
    print(f"Guardando resultados en: {RESULTADOS_PATH}")
    print(f"Empezando a las {datetime.now().strftime('%H:%M:%S')}\n")
    sys.stdout.flush()

    for i, item in enumerate(pendientes, start=1):
        resultado = evaluar_pregunta(item)

        with open(RESULTADOS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(resultado, ensure_ascii=False) + "\n")

        estado = resultado.get("clasificacion", "?")
        duracion = resultado.get("duracion_segundos", "?")
        print(f"[{i}/{len(pendientes)}] id={item['id']} ({item['categoria']}) -> {estado} ({duracion}s)")
        sys.stdout.flush()

    print(f"\nTerminado a las {datetime.now().strftime('%H:%M:%S')}. Total en {RESULTADOS_PATH}: {len(ids_ya_hechos) + len(pendientes)}")


if __name__ == "__main__":
    main()
