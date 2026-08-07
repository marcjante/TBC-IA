"""
TBC-AI - Generador de respuestas para el Banco de 360 preguntas de pacientes
Usa /api/patient-chat (lenguaje sencillo). Guarda progreso incrementalmente.
"""

import requests
import json
import os
import time
from datetime import datetime

API_URL = "http://127.0.0.1:8000"
PROGRESS_FILE = "faq_bank_progress.json"
OUTPUT_MD = "Banco_360_respuestas.md"

BANK = {
    "1. Antes del diagnóstico": {
        "¿Qué es la tuberculosis?": [
            "¿Qué es exactamente la tuberculosis?",
            "¿Es lo mismo TBC que tuberculosis?",
            "¿Por qué se llama así, tuberculosis?",
            "No entiendo qué enfermedad es esta, ¿me lo explicas?",
            "¿Es una infección grave?",
            "¿Qué le pasa a mi cuerpo si tengo tuberculosis?",
        ],
        "Síntomas": [
            "¿Qué síntomas tiene la tuberculosis?",
            "Llevo tosiendo semanas, ¿puede ser TBC?",
            "¿Es normal sudar tanto por la noche?",
            "He perdido peso sin motivo, ¿tiene que ver?",
            "¿La tuberculosis da fiebre siempre?",
            "¿Puedo tener tuberculosis y no notar nada?",
        ],
        "Formas de contagio": [
            "¿Cómo se contagia la tuberculosis?",
            "¿Se pega por el aire?",
            "¿Me puedo contagiar dando un abrazo?",
            "¿Se contagia comiendo del mismo plato?",
            "¿Cuánto tiempo hay que estar cerca de alguien para contagiarse?",
            "¿Los niños se contagian igual que los adultos?",
        ],
        "Factores de riesgo": [
            "¿Por qué me ha dado a mí esta enfermedad?",
            "¿Hay gente con más riesgo de tener tuberculosis?",
            "¿Fumar aumenta el riesgo?",
            "¿Tener las defensas bajas influye?",
            "¿Es más frecuente en algunos países?",
            "¿Vivir con muchas personas en casa aumenta el riesgo?",
        ],
        "Cuándo consultar": [
            "¿Cuándo debería ir al médico por esto?",
            "Llevo tos más de tres semanas, ¿tengo que consultar?",
            "¿Hace falta ir a urgencias o puedo esperar a mi médico de cabecera?",
            "¿Cómo sé si lo que tengo es grave?",
            "¿Debo consultar aunque no tenga fiebre?",
            "¿A qué especialista tengo que ir?",
        ],
        "Pruebas iniciales": [
            "¿Qué pruebas me van a hacer para saber si tengo tuberculosis?",
            "¿Me van a hacer una radiografía?",
            "¿Qué es eso de escupir en un bote para analizarlo?",
            "¿Duele la prueba de la piel?",
            "¿Cuánto tardan en darme los resultados?",
            "¿Tengo que estar en ayunas para las pruebas?",
        ],
    },
    "2. Tras el diagnóstico": {
        "¿Tiene cura?": [
            "¿La tuberculosis se cura del todo?",
            "¿Me voy a curar seguro?",
            "¿Cuánta gente se cura de esto?",
            "¿Puedo morir de tuberculosis?",
            "¿Hay casos que no se curan?",
            "¿Con el tratamiento correcto siempre se cura?",
        ],
        "Pronóstico": [
            "¿Qué va a pasar a partir de ahora?",
            "¿Voy a quedar con secuelas?",
            "¿Podré hacer vida normal después?",
            "¿Cuánto tiempo voy a estar enfermo?",
            "¿Me va a quedar el pulmón dañado?",
            "¿Puede volver la enfermedad después de curarme?",
        ],
        "Aislamiento": [
            "¿Tengo que estar aislado en casa?",
            "¿Durante cuánto tiempo no puedo salir?",
            "¿Puedo dormir con mi pareja mientras estoy contagioso?",
            "¿Tengo que comer en una habitación aparte?",
            "¿Cuándo dejo de ser un riesgo para los demás?",
            "¿Puedo recibir visitas en casa?",
        ],
        "Comunicar a familiares": [
            "¿Tengo que decírselo a toda mi familia?",
            "¿Cómo se lo explico a mis hijos?",
            "¿Es obligatorio avisar a la gente con la que he estado?",
            "¿Quién avisa a mis contactos, yo o el hospital?",
            "Me da vergüenza contarlo, ¿qué hago?",
            "¿Tengo que decírselo a mi jefe?",
        ],
        "Duración del tratamiento": [
            "¿Cuánto dura el tratamiento?",
            "¿Por qué tengo que tomar la medicación tantos meses?",
            "¿Puedo dejarlo antes si me encuentro bien?",
            "¿El tratamiento es siempre igual de largo para todos?",
            "¿Qué pasa si se me alarga el tratamiento?",
            "¿Hay tratamientos más cortos?",
        ],
        "Seguimiento": [
            "¿Cada cuánto tengo que ir a revisión?",
            "¿Qué controles me van a hacer durante el tratamiento?",
            "¿Cuándo sabré que estoy curado del todo?",
            "¿Necesito analíticas con frecuencia?",
            "¿Me van a repetir la radiografía?",
            "¿Qué pasa si falto a una revisión?",
        ],
    },
    "3. Medicación": {
        "Cómo tomar los fármacos": [
            "¿Cómo tengo que tomarme las pastillas?",
            "¿Es mejor con el estómago vacío?",
            "¿Puedo tomarlas con el desayuno?",
            "¿A qué hora es mejor tomarlas?",
            "¿Tengo que tomarlas siempre a la misma hora?",
            "¿Puedo tomar todas las pastillas juntas de golpe?",
        ],
        "Olvido de dosis": [
            "Se me olvidó tomar la medicación esta mañana, ¿qué hago?",
            "¿Qué pasa si me salto un día?",
            "Si me acuerdo por la noche, ¿me la tomo igual?",
            "¿Es grave olvidar una dosis de vez en cuando?",
            "¿Tengo que doblar la dosis si me la salté ayer?",
            "¿Cómo puedo acordarme mejor de tomarla?",
        ],
        "Vómitos tras la toma": [
            "He vomitado justo después de tomar la pastilla, ¿me la vuelvo a tomar?",
            "¿Es normal tener náuseas con esta medicación?",
            "¿Qué hago si vomito siempre después de tomarla?",
            "¿Puedo tomar algo para las náuseas?",
            "¿Debo avisar si vomito mucho?",
            "¿El vómito hace que el tratamiento no funcione?",
        ],
        "Interacciones": [
            "¿Puedo tomar paracetamol con este tratamiento?",
            "¿Interfiere con los anticonceptivos?",
            "¿Puedo tomar ibuprofeno si me duele algo?",
            "¿Puedo tomar mi medicación habitual de la tensión?",
            "¿Hay algo que no pueda tomar mientras hago este tratamiento?",
            "¿Puedo tomar vitaminas o suplementos?",
        ],
        "Conservación": [
            "¿Cómo tengo que guardar las pastillas?",
            "¿Se pueden guardar en la nevera?",
            "¿Aguantan bien con el calor del verano?",
            "¿Puedo llevarlas en el bolso todo el día?",
            "¿Qué hago si se me han mojado las pastillas?",
            "¿Caducan pronto?",
        ],
        "Diferencias entre medicamentos": [
            "¿Para qué sirve cada pastilla que me han dado?",
            "¿Por qué tomo varias medicinas distintas a la vez?",
            "¿Todas hacen lo mismo o cada una algo diferente?",
            "¿Puedo dejar de tomar una si me sienta mal, pero seguir con las otras?",
            "¿Cuál es la más importante de todas?",
            "¿Por qué cambian a veces la combinación de pastillas?",
        ],
    },
    "4. Efectos adversos": {
        "Náuseas": [
            "Tengo náuseas todos los días, ¿es por la medicación?",
            "¿Se me pasarán las náuseas con el tiempo?",
            "¿Puedo tomar algo para las náuseas?",
            "¿Es peligroso tener tantas náuseas?",
            "¿Debo comer algo especial para que no me siente tan mal?",
            "¿A partir de cuándo debo preocuparme por las náuseas?",
        ],
        "Orina naranja": [
            "¿Por qué se me ha puesto la orina naranja?",
            "¿Es normal o debo preocuparme?",
            "¿También se me van a manchar las lágrimas o el sudor?",
            "¿Mancha la ropa interior?",
            "¿Esto significa que el hígado me está fallando?",
            "¿Cuánto va a durar esto de la orina de color?",
        ],
        "Erupciones": [
            "Me han salido manchas en la piel, ¿es por el tratamiento?",
            "¿Tengo que dejar de tomar la medicación si me sale un sarpullido?",
            "¿Es peligrosa una reacción en la piel?",
            "¿Qué hago si me pica mucho la piel?",
            "¿Puedo ponerme crema para las manchas?",
            "¿Cuándo debo ir a urgencias por una erupción?",
        ],
        "Visión borrosa": [
            "Veo un poco borroso desde que tomo la medicación, ¿es normal?",
            "¿Puede afectarme a la vista el tratamiento?",
            "¿Tengo que ir al oculista?",
            "¿Es grave si no distingo bien los colores?",
            "¿Se me va a pasar la vista borrosa al terminar el tratamiento?",
            "¿Debo parar la medicación si veo mal?",
        ],
        "Dolor abdominal": [
            "Me duele mucho la barriga desde que empecé el tratamiento, ¿es normal?",
            "¿El dolor de estómago es por las pastillas?",
            "¿Puedo tomar algo para el dolor de barriga?",
            "¿Cuándo el dolor abdominal es motivo de urgencia?",
            "¿Es normal tener molestias digestivas con este tratamiento?",
            "¿Debo comer distinto si me duele la tripa?",
        ],
        "Cuándo acudir a urgencias": [
            "¿Qué síntomas son motivo de ir a urgencias?",
            "¿Tener la piel amarilla es urgente?",
            "¿Y si tengo mucha fiebre de golpe?",
            "¿La sangre al toser es motivo de urgencias?",
            "¿Cómo distingo un efecto normal de uno grave?",
            "¿A quién llamo si tengo dudas fuera de horario?",
        ],
    },
    "5. Contagio y prevención": {
        "Convivencia": [
            "¿Puedo seguir viviendo con mi familia mientras tengo tuberculosis?",
            "¿Tengo que dormir en una habitación separada?",
            "¿Podemos compartir el baño?",
            "¿Debo lavar mi ropa aparte de la del resto?",
            "¿Puedo cocinar para toda la familia?",
            "¿Hay que desinfectar la casa de alguna forma especial?",
        ],
        "Mascarilla": [
            "¿Tengo que llevar mascarilla en casa?",
            "¿Durante cuánto tiempo debo usar mascarilla?",
            "¿Qué tipo de mascarilla es la adecuada?",
            "¿Cuándo puedo dejar de usarla?",
            "¿Tengo que usarla también al dormir?",
            "¿Es obligatorio llevarla si salgo a la calle?",
        ],
        "Trabajo": [
            "¿Puedo ir a trabajar mientras tengo tuberculosis?",
            "¿Necesito una baja laboral?",
            "¿Cuándo podré volver al trabajo?",
            "¿Tengo que contárselo a mi empresa?",
            "¿Si trabajo con gente puedo contagiarles?",
            "¿Quién decide si estoy en condiciones de volver a trabajar?",
        ],
        "Escuela": [
            "¿Puede mi hijo ir al colegio si tiene tuberculosis?",
            "¿Hay que avisar al centro escolar?",
            "¿Los compañeros de clase corren riesgo?",
            "¿Cuándo puede volver a clase?",
            "¿Van a hacerle pruebas a otros niños del colegio?",
            "¿Puede hacer educación física mientras está en tratamiento?",
        ],
        "Viajes": [
            "¿Puedo viajar mientras estoy en tratamiento?",
            "¿Puedo coger un avión?",
            "¿Necesito algún informe médico para viajar?",
            "¿Hay riesgo de contagiar a otros pasajeros?",
            "¿Puedo salir del país durante el tratamiento?",
            "¿Debo avisar a alguien antes de viajar?",
        ],
        "Mascotas": [
            "¿Puede contagiarse mi perro?",
            "¿Y mi gato, corre riesgo?",
            "¿Tengo que alejarme de mis mascotas?",
            "¿Puedo seguir durmiendo con mi mascota?",
            "¿Los animales pueden contagiarme algo a mí también?",
            "¿Hay que llevar a la mascota al veterinario por esto?",
        ],
    },
    "6. Vida diaria": {
        "Alimentación": [
            "¿Tengo que seguir una dieta especial?",
            "¿Hay alimentos que debo evitar?",
            "¿Qué comidas me ayudan a recuperarme antes?",
            "¿Puedo comer de todo con el tratamiento?",
            "¿Necesito tomar algún suplemento alimenticio?",
            "¿Debo comer más porque he perdido peso?",
        ],
        "Alcohol": [
            "¿Puedo beber alcohol durante el tratamiento?",
            "¿Una cerveza de vez en cuando me hace daño?",
            "¿Por qué no puedo beber con esta medicación?",
            "¿Cuándo podré volver a beber con normalidad?",
            "¿El alcohol afecta al hígado más de lo normal con este tratamiento?",
            "¿Puedo brindar en una celebración especial?",
        ],
        "Tabaco": [
            "¿Puedo fumar mientras tengo tuberculosis?",
            "¿Fumar empeora la enfermedad?",
            "¿Debería dejar de fumar ahora?",
            "¿El tabaco interfiere con la medicación?",
            "¿Fumar retrasa la curación?",
            "¿Puedo vapear en vez de fumar tabaco normal?",
        ],
        "Ejercicio": [
            "¿Puedo hacer ejercicio con tuberculosis?",
            "¿Es malo esforzarme físicamente durante el tratamiento?",
            "¿Cuándo podré volver al gimnasio?",
            "¿Puedo salir a correr?",
            "¿El deporte me puede hacer sentir peor?",
            "¿Hay algún ejercicio que me venga bien mientras estoy enfermo?",
        ],
        "Sexo": [
            "¿Puedo tener relaciones sexuales con mi pareja?",
            "¿Le puedo contagiar a mi pareja teniendo sexo?",
            "¿Tengo que usar protección por la tuberculosis?",
            "¿Cuándo es seguro volver a tener relaciones sin preocuparme?",
            "¿Afecta el tratamiento a mi deseo sexual?",
            "¿Debo hablar con mi pareja antes de tener relaciones?",
        ],
        "Embarazo y lactancia": [
            "¿Puedo quedarme embarazada mientras tomo este tratamiento?",
            "Estoy embarazada y me han diagnosticado tuberculosis, ¿qué hago?",
            "¿Puedo dar el pecho a mi bebé?",
            "¿Le puede pasar algo a mi bebé por mi enfermedad?",
            "¿Hay medicamentos prohibidos durante el embarazo?",
            "¿El parto puede verse afectado por el tratamiento?",
        ],
    },
    "7. Revisiones y pruebas": {
        "Analíticas": [
            "¿Para qué me hacen análisis de sangre tan a menudo?",
            "¿Qué miran exactamente en la analítica?",
            "¿Tengo que ir en ayunas a la extracción?",
            "¿Cuándo me darán los resultados?",
            "¿Qué pasa si sale algo alterado en la analítica?",
            "¿Con qué frecuencia me repetirán las analíticas?",
        ],
        "Radiografías": [
            "¿Cada cuánto me harán radiografías de tórax?",
            "¿Por qué necesito tantas radiografías?",
            "¿Es peligrosa tanta radiación acumulada?",
            "¿Qué buscan exactamente en la radiografía?",
            "¿Me dirán el resultado el mismo día?",
            "¿La radiografía sirve para saber si ya estoy curado?",
        ],
        "Cultivos": [
            "¿Qué es el cultivo que me han pedido?",
            "¿Por qué tarda tanto en dar resultado?",
            "¿Para qué sirve repetir el cultivo?",
            "¿Un cultivo negativo significa que ya estoy curado?",
            "¿Tengo que dar varias muestras?",
            "¿Cómo se hace exactamente esa prueba?",
        ],
        "PCR": [
            "¿Qué diferencia hay entre la PCR y el cultivo?",
            "¿La PCR tarda menos en dar resultado?",
            "¿Qué significa que la PCR haya salido positiva?",
            "¿Me tienen que repetir la PCR?",
            "¿Es fiable al cien por cien la PCR?",
            "¿Qué pasa si la PCR y el cultivo dan resultados distintos?",
        ],
        "Baciloscopia": [
            "¿Qué es la baciloscopia que me van a hacer?",
            "¿Duele o es una prueba sencilla?",
            "¿Qué significa que la baciloscopia sea positiva?",
            "¿Con eso ya saben si soy contagioso?",
            "¿Cuántas veces me la van a repetir?",
            "¿Cuándo pasa la baciloscopia de positiva a negativa?",
        ],
        "Finalización del tratamiento": [
            "¿Cómo sabré que ya he terminado el tratamiento?",
            "¿Qué pruebas me harán al final?",
            "¿Me darán un informe de que estoy curado?",
            "¿Necesito revisiones después de terminar?",
            "¿Puedo recaer después de haber terminado bien el tratamiento?",
            "¿Qué debo hacer si noto síntomas después de haber terminado?",
        ],
    },
    "8. Situaciones especiales": {
        "VIH": [
            "Tengo VIH además de tuberculosis, ¿cambia algo mi tratamiento?",
            "¿Puedo tomar la medicación de VIH junto con la de tuberculosis?",
            "¿Tengo más riesgo por tener las dos enfermedades a la vez?",
            "¿Hay que coordinar las citas de las dos especialidades?",
            "¿El tratamiento de tuberculosis dura más si tengo VIH?",
            "¿Debo avisar a mi especialista de VIH sobre la tuberculosis?",
        ],
        "Diabetes": [
            "Tengo diabetes, ¿afecta esto a mi tratamiento de tuberculosis?",
            "¿La tuberculosis puede descontrolar mi azúcar?",
            "¿Tengo que controlarme el azúcar más a menudo ahora?",
            "¿Puedo tomar mi medicación de la diabetes junto con la de tuberculosis?",
            "¿La diabetes hace que tarde más en curarme?",
            "¿Debo avisar a mi médico de diabetes sobre este tratamiento?",
        ],
        "Niños": [
            "¿El tratamiento es igual para los niños que para los adultos?",
            "¿Cómo le doy la medicación a mi hijo pequeño?",
            "¿Es más peligrosa la tuberculosis en niños?",
            "¿Qué síntomas debo vigilar en mi hijo?",
            "¿Puede mi hijo hacer vida normal en el colegio?",
            "¿Hay pastillas especiales para niños pequeños?",
        ],
        "Mayores": [
            "Mi madre es mayor, ¿el tratamiento es igual para ella?",
            "¿Hay más riesgo de efectos secundarios en personas mayores?",
            "¿Cómo puedo ayudar a que no se le olvide la medicación?",
            "¿Es más difícil curarse siendo mayor?",
            "¿Necesita más controles por su edad?",
            "¿Puede vivir sola durante el tratamiento?",
        ],
        "Inmunosupresión": [
            "Tomo medicación que baja mis defensas, ¿es más grave para mí?",
            "¿Tengo que dejar mi tratamiento habitual mientras tomo el de tuberculosis?",
            "¿Tengo más riesgo de complicaciones?",
            "¿Debo avisar al especialista que me trata mi otra enfermedad?",
            "¿El tratamiento de tuberculosis dura más si estoy inmunodeprimido?",
            "¿Puedo estar cerca de otras personas si tengo las defensas bajas?",
        ],
        "Tuberculosis resistente": [
            "Me han dicho que tengo tuberculosis resistente, ¿qué significa?",
            "¿Es más grave que la tuberculosis normal?",
            "¿Por qué no me funcionan las pastillas de siempre?",
            "¿El tratamiento dura más si es resistente?",
            "¿Tiene cura la tuberculosis resistente?",
            "¿Por qué me han cambiado la medicación?",
        ],
    },
    "9. Apoyo emocional": {
        "Miedo": [
            "Tengo mucho miedo desde que me lo diagnosticaron, ¿es normal?",
            "¿Me voy a morir de esto?",
            "No puedo dejar de pensar en la enfermedad, ¿qué hago?",
            "¿Es normal tener miedo a contagiar a mi familia?",
            "¿Con quién puedo hablar de mis miedos?",
            "¿El miedo que siento puede afectar a mi recuperación?",
        ],
        "Ansiedad": [
            "Desde el diagnóstico no puedo dormir por la ansiedad, ¿qué hago?",
            "¿Es normal sentirme tan agobiado?",
            "¿Puedo pedir ayuda psicológica durante el tratamiento?",
            "La ansiedad no me deja concentrarme en nada, ¿es por la enfermedad?",
            "¿La medicación puede aumentarme la ansiedad?",
            "¿Hay algo que pueda hacer yo mismo para sentirme mejor?",
        ],
        "Estigma": [
            "Me da vergüenza que la gente sepa que tengo tuberculosis, ¿es normal sentir esto?",
            "¿La gente me va a rechazar si se entera?",
            "¿Tengo obligación de contárselo a todo el mundo?",
            "Siento que me van a mirar mal en el trabajo, ¿qué hago?",
            "¿Cómo le explico a la gente que ya no soy contagioso?",
            "¿Hay algún apoyo para gente que se siente señalada por esto?",
        ],
        "Familia": [
            "Mi familia está muy preocupada, ¿cómo les tranquilizo?",
            "¿Cómo le explico esto a mis hijos pequeños?",
            "Mi pareja tiene miedo de contagiarse, ¿qué le digo?",
            "¿Es normal que mi familia también esté afectada emocionalmente?",
            "¿Puede venir mi familia a las visitas conmigo?",
            "¿Hay información pensada para explicarle esto a los niños?",
        ],
        "Trabajo": [
            "Tengo miedo de perder mi trabajo por esta enfermedad, ¿puede pasar?",
            "¿Cómo le explico a mi jefe lo que tengo sin dar demasiados detalles?",
            "¿Tengo derecho a que no me despidan por estar de baja?",
            "Me preocupa que mis compañeros me traten distinto, ¿qué hago?",
            "¿Puedo pedir que se mantenga en confidencialidad?",
            "¿Cuándo debería hablar con recursos humanos?",
        ],
        "Recursos de ayuda": [
            "¿Hay algún grupo de apoyo para personas con tuberculosis?",
            "¿Puedo hablar con un psicólogo del hospital?",
            "¿Hay asociaciones de pacientes que puedan ayudarme?",
            "¿A quién puedo llamar si me siento muy mal anímicamente?",
            "¿Existen recursos de ayuda económica durante el tratamiento?",
            "¿Puedo pedir apoyo social además del médico?",
        ],
    },
    "10. Casos prácticos": {
        "Olvido de medicación": [
            "Se me olvidó la pastilla de ayer, la tomo hoy junto con la de hoy?",
            "Llevo dos días sin poder tomar la medicación, ¿qué hago?",
            "¿A quién aviso si se me ha olvidado varias veces seguidas?",
            "Me quedé sin medicación este fin de semana, ¿qué hago?",
            "¿Es grave haberme saltado una dosis por error?",
            "¿Cómo retomo el tratamiento después de varios días sin tomarlo?",
        ],
        "Fiebre durante tratamiento": [
            "Tengo fiebre alta y estoy en tratamiento, ¿es normal o debo preocuparme?",
            "¿La fiebre significa que el tratamiento no está funcionando?",
            "¿Puedo tomar algo para bajar la fiebre?",
            "¿Cuándo la fiebre es motivo de ir a urgencias?",
            "Llevo varios días con fiebre baja, ¿debo avisar?",
            "¿Es normal tener fiebre al principio del tratamiento?",
        ],
        "Contacto con un bebé": [
            "Voy a estar con mi nieto recién nacido, ¿hay riesgo para él?",
            "¿Puedo coger en brazos a un bebé mientras tengo tuberculosis?",
            "¿Cuánto tiempo debo esperar para estar cerca de un recién nacido?",
            "¿Hay que hacerle pruebas al bebé si ha estado en contacto conmigo?",
            "¿Puedo besar a mi bebé durante el tratamiento?",
            "¿Es más peligroso para un bebé que para un adulto?",
        ],
        "Viaje programado": [
            "Tengo un viaje programado, ¿lo debo cancelar por la tuberculosis?",
            "¿Puedo viajar si ya llevo un tiempo de tratamiento?",
            "¿Necesito llevar la medicación conmigo en el avión?",
            "¿Qué documentación debo llevar si viajo estando en tratamiento?",
            "¿Puedo seguir el tratamiento correctamente estando de viaje?",
            "¿A quién debo avisar antes de un viaje largo?",
        ],
        "Dolor intenso": [
            "Tengo un dolor muy fuerte en el pecho, ¿es por la tuberculosis?",
            "¿Cuándo un dolor es motivo de ir a urgencias?",
            "¿Es normal tener dolor muscular con este tratamiento?",
            "¿Puedo tomar analgésicos si tengo mucho dolor?",
            "El dolor no me deja dormir, ¿qué puedo hacer?",
            "¿Debo avisar si el dolor cambia de un día para otro?",
        ],
        "Embarazo durante tratamiento": [
            "Me he quedado embarazada estando en tratamiento, ¿qué hago?",
            "¿Debo cambiar de medicación por el embarazo?",
            "¿Hay riesgo para el bebé por el tratamiento que estoy tomando?",
            "¿Puedo seguir con el mismo tratamiento durante todo el embarazo?",
            "¿A quién debo avisar primero, a mi ginecólogo o a mi neumólogo?",
            "¿El parto se puede complicar por estar en tratamiento?",
        ],
    },
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
        f"{API_URL}/api/patient-chat",
        json={"message": question, "lang": "es"},
        timeout=120,
    )
    data = resp.json()
    return data.get("response", "ERROR: sin respuesta")


def main():
    progress = load_progress()
    total = sum(len(qs) for sub in BANK.values() for qs in sub.values())
    counter = 0

    for categoria, subtemas in BANK.items():
        for subtema, preguntas in subtemas.items():
            for pregunta in preguntas:
                counter += 1
                key = f"{categoria} :: {subtema} :: {pregunta}"
                if key in progress:
                    continue
                print(f"[{counter}/{total}] {pregunta}")
                try:
                    respuesta = ask(pregunta)
                except Exception as e:
                    respuesta = f"ERROR: {str(e)}"
                progress[key] = {
                    "categoria": categoria, "subtema": subtema,
                    "pregunta": pregunta, "respuesta": respuesta,
                    "tiene_respuesta": not respuesta.strip().startswith("No encuentro"),
                }
                save_progress(progress)
                time.sleep(0.2)

    con_r = sum(1 for v in progress.values() if v["tiene_respuesta"])
    sin_r = len(progress) - con_r

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(f"# Banco de 360 preguntas - Respuestas (patient-chat)\n\n")
        f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Con respuesta: {con_r} | Sin cobertura: {sin_r}\n\n---\n\n")
        for categoria in BANK:
            f.write(f"## {categoria}\n\n")
            for key, v in progress.items():
                if v["categoria"] != categoria:
                    continue
                f.write(f"### {v['pregunta']}\n\n")
                if v["tiene_respuesta"]:
                    f.write(f"{v['respuesta']}\n\n")
                else:
                    f.write(f"*[SIN COBERTURA]* {v['respuesta']}\n\n")
                f.write("---\n\n")

    print(f"\nDocumento generado: {OUTPUT_MD}")
    print(f"Con respuesta: {con_r} | Sin cobertura: {sin_r}")


if __name__ == "__main__":
    main()
