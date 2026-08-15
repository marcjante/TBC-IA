"""
TBC-AI - backend/safety.py

Guardrails compartidos por ambos endpoints de chat (/api/chat y
/api/patient-chat):
- TB_KEYWORDS + is_tb_related(): filtro de relevancia por palabra clave,
  usado para decidir que umbral de distancia aplicar.
- LEAK_PATTERNS + detect_generic_knowledge_leak(): deteccion de respuestas
  donde el modelo "rellena" con conocimiento general en vez de limitarse
  al contexto recuperado.

FASE 7 de la auditoria: extraido de main.py sin cambiar ningun valor,
palabra clave, ni logica de deteccion. La lista TB_KEYWORDS se copia
integra (223 terminos, ampliados en 3 tandas durante la sesion de agosto
2026: vocabulario clinico base, emocional/vida cotidiana, y terminos
frecuentes detectados en el banco de 360 preguntas).
"""

TB_KEYWORDS = [
    "tubercul", "tbc", "tb ", "bacilo", "mycobacterium", "koch",
    "contagi", "contagio", "transmit", "transmis",
    "tos", "esput", "sangre al toser", "hemoptisis",
    "fiebre", "sudor", "sudo", "peso", "cansancio", "fatiga",
    "pulmon", "pulmonar", "respirat", "torax", "torácico",
    "diagnost", "baciloscopia", "cultivo", "genexpert", "pcr",
    "radiografia", "tac ", "mantoux", "tuberculina", "igra", "ppd",
    "latente", "itl", "infeccion tuberculosa",
    "tratamiento", "medicamento", "pastilla", "dosis", "farmaco",
    "isoniazida", "rifampicina", "pirazinamida", "etambutol",
    "rifapentina", "bedaquilina", "linezolid", "pretomanid",
    "efecto secundario", "efectos adversos", "higado", "hepat",
    "vista", "ojo", "orina", "sarpullido", "erupcion",
    "alcohol", "dieta", "alimentacion", "vitamina", "b6",
    "paracetamol", "ibuprofeno", "antibiotico", "anticoncept",
    "anticoagulant", "vih", "antidepresiv",
    "embaraz", "lactancia", "bebe", "pecho",
    "trabajo", "baja laboral", "colegio", "escuela", "nino",
    "viaj", "avion",
    "seguimiento", "analisis", "control",
    "resistente", "mdr", "xdr",
    "diabetes", "corticoide", "biologico", "inmunodeprimid",
    "vacuna", "bcg",
    "contacto", "familia", "familiar", "mascarilla",
    "ejercicio", "conducir", "relaciones sexuales", "dormir",
    "cocinar", "cuidar", "ventana",
    "curacion", "secuela", "recaida", "reinfect",
    "aislamiento", "aislar",
    "baar", "sensible", "resistencia",
    "alergi", "reaccion alergica",
    "miedo",
    "ansiedad",
    "estigma",
    "verguenza",
    "agobio",
    "agobiad",
    "psicolog",
    "apoyo emocional",
    "grupo de apoyo",
    "ansios",
    "abrazo",
    "abrazar",
    "beso",
    "besar",
    "dar la mano",
    "aire acondicionado",
    "mascota",
    "perro",
    "gato",
    "animal",
    "gimnasio",
    "deporte",
    "fumar",
    "tabaco",
    "cigarrillo",
    "vapear",
    "vapeo",
    "sexo",
    "pareja",
    "empresa",
    "jefe",
    "recursos humanos",
    "compañero",
    "compañeros",
    "guarderia",
    "pasaporte",
    "informe medico",
    "aeropuerto",
    "recien nacido",
    "nieto",
    "nieta",
    "abuela",
    "abuelo",
    "hijo",
    "hijos",
    "triturar",
    "conservar",
    "nevera",
    "caduca",
    "caducidad",
    "recaer",
    "curado",
    "grave",
    "gravedad",
    "morir",
    "muerte",
    "dolor",
    "vomit",
    "nausea",
    "pica",
    "borros",
    "visita",
    "analitica",
    "termin",
    "resultado",
    "mayor",
    "defensas",
    "interaccion",
    "cura",
    "curar",
    "parto",
    "aisla",
    "apoyo",
    "despid",
    "confidencial",
    "rechaz",
    "pronostico",
    "ropa",
    "bano",
    "compartir",
    "visitar",
    "riesgo",
    "urgencia",
    "amarill",
    "sangre",
    "especialista",
    "revision",
    "alta",
    "horario",
    "estomago",
    "ayunas",
    "manchas",
    "lagrimas",
    "desinfectar",
    "lejia",
    "veterinario",
    "cafe",
    "suplemento",
    "proteccion",
    "muestra",
    "azucar",
    "muscular",
    "analgesic",
    "ginecolog",
    "neumolog",
]

# Patrones que indican que el modelo esta "rellenando" con conocimiento
# general en vez de limitarse al contexto recuperado (fuga de conocimiento).
# Union de los patrones detectados historicamente en ambos endpoints de chat;
# compartida para que un patron nuevo anadido aqui proteja a los dos a la vez.
LEAK_PATTERNS = [
    "no contiene informacion especifica",
    "sin embargo, puedo ofrecerte",
    "puedo ofrecerte informacion general",
    "puedo ofrecerte",
    "puedo darte informacion general",
    "informacion general sobre",
    "de manera general,",
    "por lo general,",
    "segun mi conocimiento",
    "el texto proporcionado no",
    "el contexto no contiene",
    "no se menciona explicitamente",
]


def normalize_accents(text):
    t = text.lower()
    for a, b in [("\u00e1", "a"), ("\u00e9", "e"), ("\u00ed", "i"), ("\u00f3", "o"), ("\u00fa", "u")]:
        t = t.replace(a, b)
    return t


def detect_generic_knowledge_leak(response_text):
    normalized = normalize_accents(response_text)
    return any(normalize_accents(pat) in normalized for pat in LEAK_PATTERNS)


def is_tb_related(text):
    normalized = text.lower()
    normalized = normalized.replace("?", " ").replace("!", " ").replace(".", " ").replace(",", " ")
    normalized = " " + normalized + " "
    return any((" " + kw if not kw.endswith(" ") else kw) in normalized for kw in TB_KEYWORDS) or any(kw.strip() in normalized for kw in TB_KEYWORDS)
