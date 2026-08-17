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

# Frases del propio reflejo de seguridad generico del modelo (rechazo tipo
# "no puedo dar asistencia medica"), distinto de la frase fija oficial del
# sistema ("No encuentro esta informacion..."). Detectado en produccion en
# la sesion de agosto 2026: el modelo respondio con un rechazo generico de
# este tipo pese a tener 8 fragmentos de contexto relevantes disponibles,
# y el guardrail de LEAK_PATTERNS no lo capturaba por no ser un caso de
# "relleno con conocimiento general" sino de rechazo directo. Las frases
# se han elegido para ser lo bastante especificas del patron de rechazo
# como para no confundirse con un recordatorio legitimo dentro de una
# respuesta bien fundamentada (p. ej. "consulta a tu equipo medico" al
# final de una respuesta con fuentes citadas no activa este guard).
REFUSAL_PATTERNS = [
    "no puedo proporcionar asistencia medica",
    "no puedo proporcionar diagnosticos",
    "no puedo dar diagnosticos",
    "no puedo brindar diagnosticos",
    "no puedo ofrecer diagnosticos",
    "no puedo dar asistencia medica",
    "no puedo brindar asistencia medica",
    "no puedo ofrecer asistencia medica",
    "lo siento, pero no puedo",
    "como modelo de lenguaje, no puedo",
    "no estoy programado para dar consejos medicos",
    "no estoy capacitado para dar consejos medicos",
]


def normalize_accents(text):
    t = text.lower()
    for a, b in [("\u00e1", "a"), ("\u00e9", "e"), ("\u00ed", "i"), ("\u00f3", "o"), ("\u00fa", "u")]:
        t = t.replace(a, b)
    return t


def detect_generic_knowledge_leak(response_text):
    normalized = normalize_accents(response_text)
    return any(normalize_accents(pat) in normalized for pat in LEAK_PATTERNS)


def detect_model_refusal(response_text):
    """Detecta cuando el propio modelo rechaza responder con su reflejo
    generico de seguridad ('no puedo dar asistencia medica'), en vez de
    seguir las reglas del sistema (responder con el contexto, o usar la
    frase fija oficial si no hay informacion suficiente). Un rechazo de
    este tipo debe tratarse igual que una fuga: sustituirse por la frase
    fija y vaciar las fuentes, para no mostrar una respuesta contradictoria
    (dice que no puede ayudar, pero adjunta fuentes)."""
    normalized = normalize_accents(response_text)
    return any(normalize_accents(pat) in normalized for pat in REFUSAL_PATTERNS)


# Variantes de "no lo se" expresadas por el modelo con sus propias palabras,
# en vez de usar la frase fija exacta del sistema. Hasta agosto 2026, esta
# lista solo se usaba en /api/patient-chat; /api/chat solo comprobaba el
# prefijo literal "No encuentro esta informaci", una deteccion mas estrecha
# que dejaba pasar sin normalizar variantes como "No tengo esta informacion"
# en el endpoint usado por profesionales. Unificada aqui para que ambos
# endpoints detecten exactamente los mismos casos.
NO_INFO_VARIANTS = [
    "no encuentro esta informacion", "no encuentro informacion",
    "no tengo esta informacion", "no tengo informacion",
    "no dispongo de esta informacion", "no dispongo de informacion",
    "no cuento con esta informacion", "no cuento con informacion",
]


def detect_no_info_statement(response_text):
    normalized = normalize_accents(response_text)
    return any(variant in normalized for variant in NO_INFO_VARIANTS)


def is_tb_related(text):
    normalized = text.lower()
    normalized = normalized.replace("?", " ").replace("!", " ").replace(".", " ").replace(",", " ")
    normalized = " " + normalized + " "
    return any((" " + kw if not kw.endswith(" ") else kw) in normalized for kw in TB_KEYWORDS) or any(kw.strip() in normalized for kw in TB_KEYWORDS)
