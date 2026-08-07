"""
TBC-AI - Generador de FAQ de pacientes
Envia cada una de las 200+ preguntas al endpoint /api/chat local y guarda
el progreso incrementalmente (JSON) para poder reanudar si se interrumpe.
Al final compila un Markdown organizado por categoria.
"""

import requests
import json
import os
import time
from datetime import datetime

API_URL = "http://127.0.0.1:8000"
PROGRESS_FILE = "faq_progress.json"
OUTPUT_MD = "FAQ_pacientes_tuberculosis.md"

CATEGORIAS = {
    "1. Que es la tuberculosis": [
        "Que es la tuberculosis?",
        "Que la produce?",
        "Es un virus o una bacteria?",
        "Como se contagia?",
        "Por que la llaman TBC?",
        "La tuberculosis tiene cura?",
        "Es una enfermedad grave?",
        "Cuanta gente la tiene?",
        "Se puede morir por tuberculosis?",
        "Que organos puede afectar?",
    ],
    "2. Contagio": [
        "Como me he contagiado?",
        "Cuanto tiempo hace que me infecte?",
        "Puedo contagiar a mi familia?",
        "Puedo besar a mi pareja?",
        "Se transmite por la saliva?",
        "Se contagia por compartir cubiertos?",
        "Se transmite por la ropa?",
        "Se contagia por abrazar?",
        "Se contagia por dar la mano?",
        "Se contagia por compartir el bano?",
        "Puede contagiarse mi mascota?",
        "Puede contagiarme mi perro?",
        "Y mi gato?",
        "El aire acondicionado contagia?",
        "Las mascarillas protegen?",
        "Tengo que dormir solo?",
        "Tengo que aislarme?",
        "Durante cuanto tiempo soy contagioso?",
        "Cuando dejo de contagiar?",
        "Puedo ir a visitar a mis padres?",
    ],
    "3. Sintomas": [
        "Cuales son los sintomas?",
        "Siempre produce tos?",
        "Puedo tener tuberculosis sin fiebre?",
        "La perdida de peso es normal?",
        "Por que sudo por la noche?",
        "Es normal tener sangre al toser?",
        "La tuberculosis produce dolor?",
        "Puede producir cansancio?",
        "Puede no dar sintomas?",
        "La tuberculosis siempre afecta al pulmon?",
    ],
    "4. Diagnostico": [
        "Como saben que tengo tuberculosis?",
        "Que significa una baciloscopia positiva?",
        "Que significa una PCR positiva?",
        "Que es el GeneXpert?",
        "Que diferencia hay entre cultivo y PCR?",
        "Cuanto tarda un cultivo?",
        "Que es una radiografia compatible?",
        "Necesito un TAC?",
        "Que significa una prueba de tuberculina positiva?",
        "Que es el IGRA?",
        "Que diferencia hay entre Mantoux e IGRA?",
        "Puedo tener una prueba positiva sin estar enfermo?",
        "Que significa infeccion latente?",
    ],
    "5. Tuberculosis latente": [
        "Que es la tuberculosis latente?",
        "Es contagiosa?",
        "Necesita tratamiento?",
        "Que riesgo tengo de desarrollar enfermedad?",
        "Puede desaparecer sola?",
        "Como se si es latente o activa?",
        "Durante cuanto tiempo dura?",
    ],
    "6. Tratamiento": [
        "Cuanto dura el tratamiento?",
        "Por que son tantos medicamentos?",
        "Que pasa si olvido una dosis?",
        "Que hago si vomito despues de tomar la medicacion?",
        "Tengo que tomarla en ayunas?",
        "Puedo tomarla con comida?",
        "Puedo partir las pastillas?",
        "Hay tratamiento liquido?",
        "Cuando empezare a notar mejoria?",
        "Que ocurre si dejo el tratamiento antes?",
    ],
    "7. Medicamentos": [
        "Para que sirve la isoniazida?",
        "Para que sirve la rifampicina?",
        "Para que sirve la pirazinamida?",
        "Para que sirve el etambutol?",
        "Por que tomo cuatro medicamentos?",
        "Que es la rifapentina?",
        "Que es la bedaquilina?",
        "Que es el linezolid?",
        "Que es el pretomanid?",
        "Que medicamentos son los mas importantes?",
    ],
    "8. Efectos secundarios": [
        "Es normal tener nauseas?",
        "Es normal que la orina sea naranja?",
        "La rifampicina tine las lagrimas?",
        "Puedo usar lentillas?",
        "Que hago si aparece un sarpullido?",
        "Puede afectar al higado?",
        "Que sintomas indican dano hepatico?",
        "Que pasa si me pican las manos?",
        "Puede afectar a la vista?",
        "Cuando debo acudir a urgencias?",
    ],
    "9. Alcohol y alimentacion": [
        "Puedo beber alcohol?",
        "Que alimentos debo evitar?",
        "Necesito una dieta especial?",
        "Puedo tomar cafe?",
        "Puedo tomar vitaminas?",
        "Necesito vitamina B6?",
        "Puedo tomar suplementos?",
        "Que alimentos ayudan a recuperarme?",
    ],
    "10. Interacciones": [
        "Puedo tomar paracetamol?",
        "Puedo tomar ibuprofeno?",
        "Puedo tomar antibioticos?",
        "La rifampicina disminuye el efecto de otros medicamentos?",
        "Puedo tomar anticonceptivos?",
        "Puedo tomar anticoagulantes?",
        "Interfiere con medicamentos para el VIH?",
        "Interfiere con antidepresivos?",
    ],
    "11. Embarazo y lactancia": [
        "Puedo quedarme embarazada?",
        "Estoy embarazada, que pasa?",
        "Puedo dar el pecho?",
        "Mi bebe corre riesgo?",
        "Hay medicamentos prohibidos?",
    ],
    "12. Trabajo": [
        "Cuando puedo volver al trabajo?",
        "Necesito una baja laboral?",
        "Quien decide el alta?",
        "Puedo trabajar si llevo mascarilla?",
        "Que pasa si trabajo en un hospital?",
    ],
    "13. Escuela y ninos": [
        "Puede ir mi hijo al colegio?",
        "Hay que avisar al colegio?",
        "Hay que estudiar a toda la familia?",
        "Que pruebas haran a los ninos?",
    ],
    "14. Viajes": [
        "Puedo viajar?",
        "Puedo subir a un avion?",
        "Puedo salir del pais?",
        "Necesito llevar informes?",
    ],
    "15. Seguimiento": [
        "Cada cuanto me haran analisis?",
        "Cuando repetiran la radiografia?",
        "Cuando repetiran el cultivo?",
        "Necesito controles despues del tratamiento?",
    ],
    "16. Tuberculosis resistente": [
        "Que significa tuberculosis resistente?",
        "Que es MDR-TB?",
        "Que es XDR-TB?",
        "Es mas contagiosa?",
        "Tiene cura?",
        "Por que aparece resistencia?",
    ],
    "17. VIH y otras enfermedades": [
        "Que pasa si tengo VIH?",
        "La diabetes influye?",
        "Los corticoides aumentan el riesgo?",
        "Los tratamientos biologicos pueden reactivar la tuberculosis?",
    ],
    "18. Prevencion": [
        "Existe vacuna?",
        "Que es la BCG?",
        "Protege completamente?",
        "Como puedo evitar contagiarme?",
        "Quien debe hacerse pruebas?",
    ],
    "19. Contactos": [
        "Mi familia necesita pruebas?",
        "Que ocurre si un contacto tiene Mantoux positivo?",
        "Todos necesitan tratamiento?",
        "Quien decide si deben tratarse?",
    ],
    "20. Vida diaria": [
        "Puedo hacer ejercicio?",
        "Puedo conducir?",
        "Puedo tener relaciones sexuales?",
        "Puedo dormir con mi pareja?",
        "Puedo cocinar para mi familia?",
        "Puedo cuidar a mis hijos?",
        "Puedo cuidar a mis nietos?",
        "Debo usar mascarilla en casa?",
        "Debo abrir las ventanas?",
        "Cuando puedo dejar de usar mascarilla?",
    ],
    "21. Pronostico": [
        "Me curare completamente?",
        "Quedaran secuelas?",
        "Puede volver la tuberculosis?",
        "Como sabre que estoy curado?",
        "Puedo volver a contagiarme?",
    ],
    "22. Preguntas frecuentes sobre la medicacion": [
        "Que hago si olvido una dosis?",
        "Que hago si vomito la medicacion?",
        "Que pasa si tomo dos dosis por error?",
        "Puedo tomar toda la medicacion junta?",
        "Debo tomarla siempre a la misma hora?",
        "Que hago si me quedo sin medicacion?",
        "Puedo cambiar el horario?",
        "Puedo triturar las pastillas?",
    ],
    "23. Preguntas que hacen los familiares": [
        "Me voy a contagiar?",
        "Tengo que hacerme pruebas?",
        "Puedo cuidar al paciente?",
        "Tengo que usar mascarilla?",
        "Hay que desinfectar la casa?",
        "Hay que lavar la ropa aparte?",
        "Hay que limpiar con lejia?",
        "Que hago si tengo tos?",
    ],
    "24. Preguntas administrativas": [
        "Quien me da la baja?",
        "Necesito informar a mi empresa?",
        "Tengo que avisar al colegio?",
        "Quien paga el tratamiento?",
        "Es gratuito?",
        "Quien controla que tome la medicacion?",
    ],
    "25. Preguntas especificas para una IA clinica": [
        "Que significa este resultado de mi cultivo?",
        "Que significa BAAR positivo?",
        "Que significa GeneXpert detectado?",
        "Que significa sensible a rifampicina?",
        "Que significa resistencia a isoniazida?",
        "Que pauta me corresponde segun la guia?",
        "Que efectos secundarios requieren acudir a urgencias?",
        "Que interacciones tiene mi tratamiento?",
        "Que controles analiticos necesito?",
        "Cuando dejo de ser contagioso segun mi caso?",
        "Que hago si tengo una reaccion alergica?",
        "Puedo vacunarme durante el tratamiento?",
        "Que vacunas debo evitar?",
        "Puedo hacer deporte?",
        "Cuando puedo volver a hacer vida normal?",
        "Que debo hacer si convivo con personas inmunodeprimidas?",
    ],
}


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def ask(question):
    resp = requests.post(
        f"{API_URL}/api/chat",
        json={"message": question},
        timeout=120,
    )
    data = resp.json()
    return data.get("response", "ERROR: sin respuesta"), data.get("sources", [])


def main():
    progress = load_progress()

    total = sum(len(qs) for qs in CATEGORIAS.values())
    done = len(progress)
    print(f"Progreso previo: {done}/{total} preguntas ya respondidas.")

    counter = 0
    for categoria, preguntas in CATEGORIAS.items():
        for pregunta in preguntas:
            counter += 1
            key = f"{categoria} :: {pregunta}"

            if key in progress:
                continue

            print(f"[{counter}/{total}] {pregunta}")
            try:
                respuesta, fuentes = ask(pregunta)
            except Exception as e:
                respuesta, fuentes = f"ERROR: {str(e)}", []

            progress[key] = {
                "categoria": categoria,
                "pregunta": pregunta,
                "respuesta": respuesta,
                "fuentes": fuentes,
                "tiene_fuentes": len(fuentes) > 0,
            }
            save_progress(progress)
            time.sleep(0.3)

    print("\nTodas las preguntas procesadas. Generando documento Markdown...")

    con_respuesta = sum(1 for v in progress.values() if v["tiene_fuentes"])
    sin_respuesta = len(progress) - con_respuesta

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# FAQ de pacientes - Tuberculosis\n\n")
        f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Total de preguntas: {len(progress)}\n\n")
        f.write(f"Con respuesta basada en documentos: {con_respuesta}\n\n")
        f.write(f"Sin cobertura en documentos (requieren revision clinica manual): {sin_respuesta}\n\n")
        f.write("---\n\n")

        for categoria in CATEGORIAS:
            f.write(f"## {categoria}\n\n")
            for key, v in progress.items():
                if v["categoria"] != categoria:
                    continue
                f.write(f"### {v['pregunta']}\n\n")
                if v["tiene_fuentes"]:
                    f.write(f"{v['respuesta']}\n\n")
                    f.write("**Fuentes:**\n")
                    for s in v["fuentes"]:
                        f.write(f"- {s['category']} / {s['source']}, p.{s['page']}\n")
                else:
                    f.write("*[SIN COBERTURA EN DOCUMENTOS - requiere respuesta manual de un profesional]*\n\n")
                    f.write(f"Respuesta del sistema: {v['respuesta']}\n")
                f.write("\n---\n\n")

    print(f"\nDocumento generado: {OUTPUT_MD}")
    print(f"Con respuesta: {con_respuesta} | Sin cobertura: {sin_respuesta}")


if __name__ == "__main__":
    main()
