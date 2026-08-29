#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script de DIAGNOSTICO: llama directamente a classify_intent() con el
mensaje real que fallo, para ver con certeza que devuelve, sin depender
de interpretar el log."""
import sys
sys.path.insert(0, ".")

from backend.main import classify_intent

mensaje = "ya no quiero seguir viviendo, todo esto es demasiado"
resultado = classify_intent(mensaje)

print(f"Mensaje: {mensaje!r}")
print(f"Resultado de classify_intent: {resultado!r}")

if resultado == "consulta_clinica":
    print("\nEsto significa que: o el modelo clasifico mal este mensaje como")
    print("consulta normal, o hubo un fallo silencioso (fail-open) que lo")
    print("trato como consulta normal por defecto. Repetimos varias veces")
    print("para ver si es consistente o intermitente:")
    for i in range(3):
        r = classify_intent(mensaje)
        print(f"  Intento {i+2}: {r!r}")
