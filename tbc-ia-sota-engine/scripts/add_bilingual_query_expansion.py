#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige un hallazgo real del 23 de agosto de 2026, confirmado con datos:
la mayoria de las guias clinicas (OMS, CDC, ECDC) estan en ingles, pero
las preguntas suelen venir en español. BM25 no puede encontrar por
palabras exactas un texto en un idioma distinto al de la pregunta, y la
busqueda semantica, aunque funciona entre idiomas, no siempre acierta
con la misma precision que dentro del mismo idioma.

Confirmado con pruebas reales (test_bilingual_query.py): la misma
pregunta en español sola encontraba el fragmento correcto a distancia
421 (borroso); añadiendo un par de terminos clinicos en ingles a mano,
aparecian los fragmentos correctos a distancia 333-335 (mucho mas
precisos).

Cambio: expand_query() ahora tambien pide 1-2 terminos clinicos
equivalentes en ingles cuando la pregunta trata temas medicos que
probablemente esten documentados en guias en ingles, ademas de los
terminos en español que ya generaba.

Uso:
    python3 add_bilingual_query_expansion.py "/ruta/a/backend/main.py"
"""

import sys

OLD = '''QUERY_EXPANSION_SYSTEM_PROMPT = """Eres un asistente que amplia consultas de busqueda para un sistema de recuperacion de informacion medica sobre tuberculosis. Dada una pregunta de un paciente o profesional, genera de 3 a 5 terminos o frases medicas relacionadas (sinonimos, nombres alternativos, terminologia clinica formal) que ayuden a encontrar documentos relevantes, aunque la persona no use esas palabras exactas.

Responde EXCLUSIVAMENTE con los terminos adicionales separados por comas, sin explicaciones ni frases completas. Ejemplo:

Pregunta: "me duele mucho la barriga"
Respuesta: dolor abdominal, molestias gastrointestinales, dolor epigastrico

No repitas palabras que ya aparecen en la pregunta original. No inventes sintomas ni farmacos que no esten relacionados con la pregunta."""'''

NEW = '''QUERY_EXPANSION_SYSTEM_PROMPT = """Eres un asistente que amplia consultas de busqueda para un sistema de recuperacion de informacion medica sobre tuberculosis. Dada una pregunta de un paciente o profesional, genera de 3 a 5 terminos o frases medicas relacionadas (sinonimos, nombres alternativos, terminologia clinica formal) que ayuden a encontrar documentos relevantes, aunque la persona no use esas palabras exactas.

IMPORTANTE: gran parte de las guias clinicas de referencia (OMS, CDC, ECDC) estan escritas en ingles. Si la pregunta esta en español y trata un tema clinico que probablemente este documentado en esas guias (tratamiento, farmacos, dosis, efectos adversos, duracion), incluye TAMBIEN 1-2 terminos clinicos equivalentes en ingles (ej. "6-month regimen", "rifampicin", "adverse reactions") ademas de los terminos en español, para poder encontrar el texto original si la busqueda por palabras exactas lo necesita.

Responde EXCLUSIVAMENTE con los terminos adicionales separados por comas, sin explicaciones ni frases completas. Ejemplo:

Pregunta: "cuanto dura el tratamiento de tuberculosis"
Respuesta: duracion del tratamiento, pauta terapeutica, 6-month regimen, treatment duration

No repitas palabras que ya aparecen en la pregunta original. No inventes sintomas ni farmacos que no esten relacionados con la pregunta."""'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_bilingual_query_expansion.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "IMPORTANTE: gran parte de las guias clinicas" in content:
        print("Ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(OLD)
    if count == 0:
        print("ABORTADO: no se encontró el bloque esperado. No se ha escrito nada.")
        sys.exit(1)
    if count > 1:
        print(f"ABORTADO: el bloque aparece {count} veces (debería ser único). No se ha escrito nada.")
        sys.exit(1)

    content = content.replace(OLD, NEW, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Aplicado correctamente: {path}")


if __name__ == "__main__":
    main()
