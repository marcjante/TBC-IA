#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detecta entradas de faq_bank_progress.json cuya "respuesta" es en realidad
un rechazo genérico de un modelo de lenguaje (p. ej. "Lo siento, pero no
puedo proporcionar un diagnóstico médico...") en vez de contenido clínico
real, y las separa en un informe + una copia filtrada.

No borra nada del original. Genera:
  - data/faq_bank_progress.report.txt   (lista de entradas marcadas, para revisión humana)
  - data/faq_bank_progress.cleaned.json (copia sin las entradas marcadas)

Uso:
    python scripts/filter_refusals.py
    python scripts/filter_refusals.py --input data/faq_bank_progress.json

Los patrones son deliberadamente conservadores (evitan falsos positivos en
respuestas legítimas que simplemente recomiendan consultar a un profesional,
algo común y correcto en contenido de salud). Solo marca frases que son
rechazos genéricos característicos de un LLM, no cualquier mención a
"consulta a tu médico".
"""

import argparse
import json
import re

REFUSAL_PATTERNS = [
    r"lo siento,?\s+pero no puedo proporcionar",
    r"no puedo proporcionar (un |una )?(diagnóstico|pronóstico|consejo médico)",
    r"como (modelo de lenguaje|ia|inteligencia artificial|asistente virtual)",
    r"no tengo la capacidad de (proporcionar|determinar|diagnosticar)",
    r"no hay suficiente información en el texto proporcionado",
    r"¿(hay algo más|en qué más) (en lo que )?pued[oa] ayudarte\?",
    # NOTA: el patrón que detectaba la frase canned "no encuentro esta
    # informacion en los documentos disponibles" (137 casos) se retiró a
    # propósito (agosto 2026, decisión explícita) - esas entradas se
    # conservan en el banco tal cual, sin filtrar, aunque no tengan
    # respuesta clinica real todavia.
    r"no hay una respuesta específica relacionada",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in REFUSAL_PATTERNS]


def is_refusal(respuesta: str) -> str:
    """Devuelve el patrón que coincide, o cadena vacía si no hay coincidencia."""
    for pattern, compiled in zip(REFUSAL_PATTERNS, COMPILED):
        if compiled.search(respuesta):
            return pattern
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/faq_bank_progress.json")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    flagged = {}
    clean = {}
    for key, entry in data.items():
        respuesta = entry.get("respuesta", "")
        matched_pattern = is_refusal(respuesta)
        if matched_pattern:
            flagged[key] = {"entry": entry, "matched_pattern": matched_pattern}
        else:
            clean[key] = entry

    report_path = args.input.replace(".json", ".report.txt")
    cleaned_path = args.input.replace(".json", ".cleaned.json")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Total entradas: {len(data)}\n")
        f.write(f"Marcadas como posible rechazo de modelo: {len(flagged)}\n\n")
        for key, info in flagged.items():
            entry = info["entry"]
            f.write("-" * 80 + "\n")
            f.write(f"Categoría: {entry.get('categoria', '')}\n")
            f.write(f"Pregunta:  {entry.get('pregunta', '')}\n")
            f.write(f"Respuesta: {entry.get('respuesta', '')}\n")
            f.write(f"Patrón detectado: {info['matched_pattern']}\n")

    with open(cleaned_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

    print(f"Total entradas: {len(data)}")
    print(f"Marcadas (posible rechazo de modelo): {len(flagged)}")
    print(f"Informe completo: {report_path}")
    print(f"Copia filtrada (sin las marcadas): {cleaned_path}")
    print("\nRevisa el informe antes de usar la copia filtrada — puede haber falsos positivos.")


if __name__ == "__main__":
    main()
