"""
TBC-AI - Fase 9: bateria de pruebas
Envia un conjunto de preguntas clinicas reales al endpoint /chat y guarda
las respuestas con sus fuentes en un archivo markdown para revision manual.
"""

import requests
import json
from datetime import datetime

API_URL = "http://127.0.0.1:8000"

PREGUNTAS = [
    ("Diagnostico", "Que pruebas se recomiendan para el diagnostico de tuberculosis pulmonar activa"),
    ("Diagnostico", "Cual es la diferencia entre PPD e IGRA para el diagnostico de infeccion tuberculosa"),
    ("TBC latente", "Cuales son los criterios para diagnosticar tuberculosis latente"),
    ("TBC latente", "Que pautas de tratamiento existen para la infeccion tuberculosa latente"),
    ("Tratamiento", "Cual es el esquema de tratamiento estandar para tuberculosis sensible"),
    ("Tratamiento", "Que efectos adversos son frecuentes con isoniazida y rifampicina"),
    ("Pediatria", "Como se diagnostica la tuberculosis en niños pequeños"),
    ("Embarazo", "Es seguro tratar la tuberculosis durante el embarazo"),
    ("Resistencias", "Que se considera tuberculosis multirresistente MDR-TB"),
    ("Resistencias", "Cual es el tratamiento recomendado para tuberculosis XDR"),
    ("Coinfeccion VIH", "Como se maneja la coinfeccion de tuberculosis y VIH"),
    ("Contactos", "Que protocolo se sigue para el estudio de contactos de un caso de tuberculosis"),
    ("BCG", "En que situaciones esta indicada la vacuna BCG"),
    ("Aislamiento", "Cuando se puede suspender el aislamiento respiratorio de un paciente con tuberculosis"),
    ("Pregunta fuera de alcance", "Cual es el tratamiento recomendado para la neumonia por Legionella"),
]


def main():
    resultados = []

    for i, (categoria, pregunta) in enumerate(PREGUNTAS, 1):
        print(f"[{i}/{len(PREGUNTAS)}] {categoria}: {pregunta[:60]}...")

        try:
            resp = requests.post(
                f"{API_URL}/chat",
                json={"message": pregunta},
                timeout=120,
            )
            data = resp.json()
            resultados.append({
                "categoria": categoria,
                "pregunta": pregunta,
                "respuesta": data.get("response", "ERROR: sin respuesta"),
                "sources": data.get("sources", []),
            })
        except Exception as e:
            resultados.append({
                "categoria": categoria,
                "pregunta": pregunta,
                "respuesta": f"ERROR: {str(e)}",
                "sources": [],
            })

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    output_path = f"test_results_{timestamp}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Resultados de pruebas TBC-AI - {timestamp}\n\n")
        f.write(f"Total de preguntas: {len(PREGUNTAS)}\n\n")
        f.write("---\n\n")

        for r in resultados:
            f.write(f"## [{r['categoria']}] {r['pregunta']}\n\n")
            f.write(f"**Respuesta:**\n\n{r['respuesta']}\n\n")
            if r["sources"]:
                f.write("**Fuentes:**\n\n")
                for s in r["sources"]:
                    f.write(f"- {s['category']} / {s['source']}, p.{s['page']}\n")
            else:
                f.write("**Fuentes:** (ninguna)\n")
            f.write("\n---\n\n")

    print(f"\nResultados guardados en: {output_path}")
    print("Revisalo con: open " + output_path)


if __name__ == "__main__":
    main()
