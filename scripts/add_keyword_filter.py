path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''    RELEVANCE_THRESHOLD = 650

    if not fragments or not distances or distances[0] > RELEVANCE_THRESHOLD:
        return {
            "response": "No encuentro esta informacion en los documentos disponibles.",
            "sources": [],
        }'''

new = '''    STRICT_DISTANCE_THRESHOLD = 480
    LOOSE_DISTANCE_THRESHOLD = 650

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
    ]

    def is_tb_related(text):
        normalized = text.lower()
        return any(kw in normalized for kw in TB_KEYWORDS)

    has_keyword = is_tb_related(request.message)

    if not fragments or not distances:
        return {
            "response": "No encuentro esta informacion en los documentos disponibles.",
            "sources": [],
        }

    if has_keyword:
        if distances[0] > LOOSE_DISTANCE_THRESHOLD:
            return {
                "response": "No encuentro esta informacion en los documentos disponibles.",
                "sources": [],
            }
    else:
        if distances[0] > STRICT_DISTANCE_THRESHOLD:
            return {
                "response": "No encuentro esta informacion en los documentos disponibles.",
                "sources": [],
            }'''

assert old in content, "No se encontro el bloque de umbral anterior"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Filtro combinado (palabras clave + distancia) aplicado")
