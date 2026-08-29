#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade UNA regla nueva y estrecha (regla 8) al SYSTEM_PROMPT de
/api/chat, sin tocar ni una palabra de las reglas 0-7 existentes (que
funcionan bien evitando fabricaciones, confirmado esta noche tras el
arreglo de num_ctx).

Motivo, confirmado con multiples pruebas reales el 23 de agosto de
2026: incluso con la fuente correcta en primera posicion, sin ningun
ruido delante, el modelo seguia respondiendo "no encuentro esta
informacion" ante preguntas sobre duracion del tratamiento, porque el
contexto describe una PAUTA ("regimen de 6 meses", "2HRZE/4HR") en vez
de una frase literal "el tratamiento dura X". La regla 7 ("si dudas,
elige siempre la frase fija") hacia que el modelo se negara en vez de
conectar ambas cosas.

La nueva regla 8 aclara que leer la duracion de una pauta descrita
explicitamente en el contexto NO es "rellenar con conocimiento
general" — es leer informacion que el contexto ya contiene, solo que
en otro formato. No cambia nada mas: sigue sin poder inventar farmacos,
dosis, ni datos que no esten en el contexto.

Uso:
    python3 add_regimen_duration_exception.py "/ruta/a/backend/prompts.py"
"""

import sys

OLD = '''7. La frase "No encuentro esta informacion en los documentos disponibles." es una respuesta binaria: o es tu ÚNICA respuesta completa, o no aparece en absoluto. Nunca la combines con explicaciones, disculpas, conocimiento general, ni frases como "sin embargo puedo ofrecerte..." Si dudas entre responder con el contexto o rellenar con lo que sabes, elige SIEMPRE la frase fija.
"""

PATIENT_SYSTEM_PROMPT'''

NEW = '''7. La frase "No encuentro esta informacion en los documentos disponibles." es una respuesta binaria: o es tu ÚNICA respuesta completa, o no aparece en absoluto. Nunca la combines con explicaciones, disculpas, conocimiento general, ni frases como "sin embargo puedo ofrecerte..." Si dudas entre responder con el contexto o rellenar con lo que sabes, elige SIEMPRE la frase fija.
8. EXCEPCION ESTRECHA a la regla 7: si el contexto describe una pauta o regimen terapeutico con una duracion especifica indicada explicitamente (por ejemplo "regimen de 6 meses", "2HRZE/4HR", "daily dose for 4 months"), esa duracion SI responde directamente a una pregunta sobre cuanto dura el tratamiento — no es rellenar con conocimiento general, es leer una duracion que el contexto ya indica, solo que en el formato de una pauta en vez de una frase literal "el tratamiento dura X". Usa esa duracion citando la fuente (regla 4) en vez de la frase fija de la regla 2, siempre que la pauta descrita corresponda al tipo de tuberculosis o la situacion por la que pregunta la persona. Esta excepcion NO autoriza inventar farmacos, dosis, ni datos que no esten explicitamente en el contexto.
"""

PATIENT_SYSTEM_PROMPT'''


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 add_regimen_duration_exception.py <ruta a backend/prompts.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if "EXCEPCION ESTRECHA a la regla 7" in content:
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
