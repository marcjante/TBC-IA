#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade un Clinical Safety Router DETERMINISTA (sin LLM) que se ejecuta
ANTES incluso de classify_intent(). Complementa (no sustituye) al
clasificador por LLM: cubre patrones de riesgo YA CONOCIDOS mediante
palabras clave, de forma instantanea y sin depender de que Ollama
responda de forma consistente (hoy hemos visto dos veces que el LLM
puede "distraerse" o comportarse de forma inconsistente).

Familias de reglas iniciales (segun documento de arquitectura propuesta,
agosto 2026):
  - Etambutol + sintomas visuales
  - Isoniazida + sintomas de neuropatia periferica
  - Hepatotoxicidad (orina oscura, ictericia...)
  - Sintomas cardiacos (sincope, perdida de conciencia)
  - Hemoptisis relevante
  - Sobredosis / doble dosis de medicacion

Si el LLM (classify_intent) tambien detecta una urgencia por su cuenta,
no hay conflicto: este router simplemente actua primero y mas rapido
para los casos ya conocidos.

Uso:
    python3 add_clinical_safety_router.py "/ruta/a/backend/main.py"
"""

import sys

ANCHOR = '''@app.post("/api/chat")
def chat(request: ChatRequest):
    intencion = classify_intent(request.message)'''

REPLACEMENT = '''CLINICAL_RED_FLAG_RULES = [
    {
        "id": "ethambutol_visual",
        "drugs": ["etambutol", "ethambutol"],
        "symptoms": ["borros", "veo mal", "colores diferentes", "no veo bien",
                     "pérdida de visión", "perdida de vision", "vista mal", "veo raro"],
    },
    {
        "id": "isoniazid_neuropathy",
        "drugs": ["isoniazida", "isoniacida", "isoniazid"],
        "symptoms": ["hormigueo", "entumecimiento", "quemazón", "quemazon",
                     "pies dormidos", "manos dormidas", "pies dormidos"],
    },
    {
        "id": "hepatotoxicity",
        "drugs": [],
        "symptoms": ["orina oscura", "orina marrón", "orina marron", "heces claras",
                     "piel amarilla", "ojos amarillos", "ictericia"],
    },
    {
        "id": "cardiac_symptoms",
        "drugs": [],
        "symptoms": ["me desmayé", "me desmaye", "perdida de conciencia",
                     "pérdida de conciencia", "palpitaciones fuertes"],
    },
    {
        "id": "hemoptysis_severe",
        "drugs": [],
        "symptoms": ["tos con sangre", "toso sangre", "tosiendo sangre", "tosiendo con sangre",
                     "toser sangre", "sangre al toser", "escupo sangre", "escupir sangre",
                     "sangre en el esputo", "esputo con sangre"],
    },
    {
        "id": "medication_overdose",
        "drugs": [],
        "symptoms": ["me tomé el doble", "me tome el doble", "doble dosis",
                     "dos pastillas en vez de una", "sobredosis"],
    },
]


def check_deterministic_red_flags(message):
    """Comprueba patrones de riesgo YA CONOCIDOS mediante palabras clave,
    sin depender de ningun LLM (instantaneo y 100% predecible para estos
    casos concretos). Complementa a classify_intent(), que sigue
    cubriendo framings nuevos o menos comunes.

    Devuelve el id de la regla si hay coincidencia, o None.

    LIMITACION CONOCIDA Y ACEPTADA: no detecta negaciones ("no tomo
    isoniazida" activaria igual la regla si menciona el sintoma). Se
    acepta a proposito: el coste de una falsa alarma (mensaje de
    urgencia de mas) es mucho menor que el de pasar por alto una
    emergencia real — mismo criterio que classify_intent()."""
    normalized = message.lower()
    for rule in CLINICAL_RED_FLAG_RULES:
        symptom_match = any(s in normalized for s in rule["symptoms"])
        if not symptom_match:
            continue
        if rule["drugs"] and not any(d in normalized for d in rule["drugs"]):
            continue
        return rule["id"]
    return None


@app.post("/api/chat")
def chat(request: ChatRequest):
    red_flag = check_deterministic_red_flags(request.message)
    if red_flag:
        log_usage_pattern("/api/chat", f"red_flag_{red_flag}", question=request.message)
        return {
            "response": CANNED_URGENCIA_MEDICA,
            "sources": [],
            "coverage": f"red_flag_{red_flag}",
        }

    intencion = classify_intent(request.message)'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_clinical_safety_router.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "check_deterministic_red_flags" in content:
        print("Ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(ANCHOR)
    if count == 0:
        print("ABORTADO: no se encontró el bloque esperado. No se ha escrito nada.")
        sys.exit(1)
    if count > 1:
        print(f"ABORTADO: el bloque aparece {count} veces (debería ser único). No se ha escrito nada.")
        sys.exit(1)

    content = content.replace(ANCHOR, REPLACEMENT, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Aplicado correctamente: {path}")


if __name__ == "__main__":
    main()
