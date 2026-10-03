"""
TBC-AI - backend/clinical_rules.py

Reglas clinicas DETERMINISTAS (sin LLM), revision de seguridad clinica de
octubre 2026 (ver documentacion/revisiones/2026-10-03_revision_seguridad_clinica.md):

- Signos de alarma ampliados (A4): disnea, dolor toracico, reacciones
  cutaneas graves, vomitos persistentes, confusion/convulsiones, fiebre alta
  persistente, ademas de los que ya existian. Se normalizan tildes y se
  busca por inicio de palabra.
- Interacciones farmacologicas frecuentes del tratamiento de TB (A5).
  PENDIENTE DE VALIDACION POR FARMACIA: los textos son avisos genericos de
  derivacion ("consulta con tu equipo"), nunca pautas ni dosis.
- Aviso de poblaciones en las que la pauta/duracion puede cambiar (M4).
- Deteccion de cifras clinicas (dosis, duraciones, pautas) en un texto, para
  bloquear afirmaciones no respaldadas que contengan cifras (A1).
- Comprobacion de que una traduccion conserva las cifras del original (A6).
- Validacion de citas "(Fuente: X, p.N)" contra las fuentes realmente
  usadas para generar la respuesta (A7).

Todo el texto de entrada se espera en castellano: en el chat de pacientes
los mensajes en otros idiomas se traducen al castellano antes de pasar por
estas reglas (C4).
"""

import re
import unicodedata


def normalize(text):
    """Minusculas, sin tildes ni dieresis, espacios colapsados."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _mentions(normalized_text, terms):
    """True si algun termino aparece al INICIO de una palabra (asi "tos" no
    coincide con "datos", pero "vomit" si coincide con "vomito")."""
    return any(re.search(r"(?<!\w)" + re.escape(normalize(t)), normalized_text) for t in terms)


# ------------------------------------------------------------------------------
# Signos de alarma
# ------------------------------------------------------------------------------
# Cada regla: id + sintomas (+ farmacos opcionales: si hay farmacos, hace
# falta que se mencione alguno ademas del sintoma). Se acepta que una
# negacion ("no tengo fiebre alta") active la regla: una falsa alarma es
# preferible a pasar por alto una urgencia (mismo criterio que antes).
RED_FLAG_RULES = [
    {"id": "visual_toxicity", "drugs": [], "symptoms": [
        "veo borroso", "vision borrosa", "vista borrosa", "veo mal", "no veo bien",
        "perdida de vision", "colores diferentes", "no distingo los colores",
        "veo los colores", "veo raro", "vista mal", "hi veig borros", "hi veig malament"]},
    {"id": "isoniazid_neuropathy", "drugs": ["isoniazida", "isoniacida", "isoniazid"], "symptoms": [
        "hormigueo", "entumecimiento", "quemazon", "pies dormidos", "manos dormidas"]},
    {"id": "hepatotoxicity", "drugs": [], "symptoms": [
        "orina oscura", "orina marron", "orina color coca", "heces claras", "piel amarilla",
        "ojos amarillos", "ictericia", "pell groga", "ulls grocs"]},
    {"id": "syncope_cardiac", "drugs": [], "symptoms": [
        "me desmaye", "desmayo", "perdida de conciencia", "perdi el conocimiento",
        "palpitaciones fuertes", "m'he desmaiat"]},
    {"id": "hemoptysis", "drugs": [], "symptoms": [
        "tos con sangre", "toso sangre", "tosiendo sangre", "tosiendo con sangre", "toser sangre",
        "sangre al toser", "escupo sangre", "escupir sangre", "sangre en el esputo",
        "esputo con sangre", "sangre por la boca", "tos amb sang", "tossint sang", "escupo sang"]},
    {"id": "medication_overdose", "drugs": [], "symptoms": [
        "me tome el doble", "doble dosis", "dos pastillas en vez de una", "sobredosis",
        "me he tomado todas", "he pres el doble"]},
    {"id": "respiratory_distress", "drugs": [], "symptoms": [
        "me ahogo", "me falta el aire", "falta de aire", "no puedo respirar",
        "dificultad para respirar", "dificultad respiratoria", "disnea", "respiro con dificultad",
        "m'ofego", "em falta l'aire", "no puc respirar"]},
    {"id": "chest_pain", "drugs": [], "symptoms": [
        "dolor en el pecho", "dolor de pecho", "dolor toracico", "opresion en el pecho",
        "dolor al pit", "dolor de pit"]},
    {"id": "severe_skin_or_allergic_reaction", "drugs": [], "symptoms": [
        "ampollas", "se me despega la piel", "se me pela la piel", "piel que se despega",
        "llagas en la boca", "erupcion con fiebre", "sarpullido con fiebre", "granos con fiebre",
        "se me hincha la cara", "cara hinchada", "labios hinchados", "lengua hinchada",
        "garganta hinchada", "me cuesta tragar", "butllofes"]},
    {"id": "persistent_vomiting_or_abdominal_pain", "drugs": [], "symptoms": [
        "vomito todo", "no paro de vomitar", "vomitos continuos", "vomitos persistentes",
        "no retengo nada", "dolor abdominal fuerte", "dolor fuerte de barriga",
        "dolor fuerte de estomago", "dolor muy fuerte de barriga", "no paro de vomitar"]},
    {"id": "neurological", "drugs": [], "symptoms": [
        "confusion", "confundido", "confundida", "desorientado", "desorientada", "convulsion",
        "ataque epileptico", "no se donde estoy", "me cuesta hablar", "confos", "desorientat"]},
    {"id": "high_persistent_fever", "drugs": [], "symptoms": [
        "fiebre alta", "fiebre de 39", "fiebre de 40", "fiebre que no baja", "fiebre persistente",
        "febre alta", "febre que no baixa"]},
]


def check_red_flags(*texts):
    """Devuelve el id de la primera regla que coincide en cualquiera de los
    textos (p. ej. el mensaje original y su traduccion), o None."""
    for text in texts:
        if not text:
            continue
        normalized = normalize(text)
        for rule in RED_FLAG_RULES:
            if not _mentions(normalized, rule["symptoms"]):
                continue
            if rule["drugs"] and not _mentions(normalized, rule["drugs"]):
                continue
            return rule["id"]
    return None


# ------------------------------------------------------------------------------
# Interacciones (PENDIENTE DE VALIDACION POR FARMACIA)
# ------------------------------------------------------------------------------
INTERACTION_RULES = [
    {"id": "rifamycin_contraceptives",
     "terms": ["anticonceptivo", "pildora", "anillo vaginal", "parche anticonceptivo",
               "implante anticonceptivo", "diu hormonal", "anticonceptiu"],
     "warning": ("Aviso sobre interacciones: la rifampicina y la rifapentina pueden reducir la eficacia "
                 "de los anticonceptivos hormonales (píldora, parche, anillo, implante). Mientras dure "
                 "el tratamiento y hasta que tu equipo te lo indique, usa además un método de barrera "
                 "(preservativo) y consulta qué método es el más adecuado.")},
    {"id": "rifamycin_anticoagulants",
     "terms": ["anticoagulante", "sintrom", "acenocumarol", "warfarina", "apixaban", "rivaroxaban",
               "dabigatran", "edoxaban", "anticoagulant"],
     "warning": ("Aviso sobre interacciones: la rifampicina puede disminuir mucho el efecto de los "
                 "anticoagulantes. No cambies nada por tu cuenta: tu médico debe revisar la pauta y, "
                 "con acenocumarol (Sintrom) o warfarina, controlar el INR con más frecuencia.")},
    {"id": "rifamycin_opioid_substitution",
     "terms": ["metadona", "buprenorfina", "metadona"],
     "warning": ("Aviso sobre interacciones: la rifampicina puede bajar los niveles de metadona o "
                 "buprenorfina y provocar síntomas de abstinencia. Avisa a tu equipo y a tu centro de "
                 "tratamiento para que ajusten la dosis.")},
    {"id": "rifamycin_antiretrovirals",
     "terms": ["antirretroviral", "vih", "dolutegravir", "bictegravir", "efavirenz", "darunavir",
               "ritonavir", "lopinavir", "atazanavir", "raltegravir", "biktarvy", "triumeq", "tenofovir"],
     "warning": ("Aviso sobre interacciones: muchos antirretrovirales interaccionan con la rifampicina y "
                 "la rifapentina. La pauta de ambos tratamientos debe coordinarla tu unidad de VIH junto "
                 "con tu equipo de tuberculosis; no cambies ninguna dosis por tu cuenta.")},
    {"id": "rifamycin_azoles",
     "terms": ["fluconazol", "itraconazol", "voriconazol", "posaconazol", "ketoconazol", "antifungico"],
     "warning": ("Aviso sobre interacciones: los antifúngicos azólicos (fluconazol, itraconazol, "
                 "voriconazol…) tienen interacciones importantes con la rifampicina. Consúltalo con tu "
                 "médico o farmacéutico antes de tomarlos.")},
    {"id": "antiepileptics",
     "terms": ["fenitoina", "carbamazepina", "valproato", "acido valproico", "antiepileptico", "epilepsia"],
     "warning": ("Aviso sobre interacciones: la isoniazida y la rifampicina interaccionan con varios "
                 "antiepilépticos (fenitoína, carbamazepina, valproato) y puede hacer falta controlar sus "
                 "niveles. Coméntalo con tu médico.")},
]

PYRIDOXINE_RISK_TERMS = ["embaraz", "lactancia", "diabet", "vih", "alcohol", "desnutri",
                         "insuficiencia renal", "hormigueo", "neuropatia", "vitamina b6", "piridoxina"]
ISONIAZID_TERMS = ["isoniazida", "isoniacida", "isoniazid", "rimstar", "rifinah", "rifater", "3hp", "6h", "9h"]
PYRIDOXINE_WARNING = ("Aviso: con isoniazida suele indicarse vitamina B6 (piridoxina) para prevenir la "
                      "neuropatía, sobre todo en embarazo, lactancia, diabetes, VIH, consumo de alcohol, "
                      "desnutrición o insuficiencia renal. Pregunta a tu equipo si debes tomarla.")


def interaction_warnings(*texts):
    """Avisos fijos de interacciones segun lo mencionado en la pregunta o en
    la respuesta. Se añaden diga lo que diga el LLM."""
    normalized = normalize(" ".join(t for t in texts if t))
    warnings = [r["warning"] for r in INTERACTION_RULES if _mentions(normalized, r["terms"])]
    if _mentions(normalized, ISONIAZID_TERMS) and _mentions(normalized, PYRIDOXINE_RISK_TERMS):
        warnings.append(PYRIDOXINE_WARNING)
    return warnings


# ------------------------------------------------------------------------------
# Poblaciones especiales (M4)
# ------------------------------------------------------------------------------
SPECIAL_POPULATION_TERMS = {
    "tuberculosis meníngea": ["meningea", "meningitis"],
    "tuberculosis ósea o articular": ["osea", "osteoarticular", "columna", "pott", "hueso"],
    "embarazo o lactancia": ["embaraz", "lactancia", "amamant"],
    "niños": ["nino", "nina", "hijo", "hija", "bebe", "pediatr", "menor de edad"],
    "VIH": ["vih", "sida"],
    "tuberculosis resistente": ["resistente", "multirresistente", "mdr", "xdr", "tb-rr", "rr-tb"],
}


def population_caveat(question, response):
    """Si la pregunta menciona una poblacion especial y la respuesta da cifras
    (dosis, duracion, pauta), devuelve un aviso; si no, None."""
    if not has_clinical_figures(response):
        return None
    normalized = normalize(question)
    found = [label for label, terms in SPECIAL_POPULATION_TERMS.items() if _mentions(normalized, terms)]
    if not found:
        return None
    return ("Importante: la pauta y la duración del tratamiento pueden ser distintas en esta situación ("
            + ", ".join(found) + "). Confírmalo con tu equipo de tuberculosis antes de aplicar estas cifras.")


# ------------------------------------------------------------------------------
# Cifras clinicas
# ------------------------------------------------------------------------------
_FIGURE_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|µg|ml|kg|mg/kg|%|mes|meses|semana|semanas|dia|dias|hora|horas|"
    r"veces|comprimido|comprimidos|pastilla|pastillas|dosis)\b"
    r"|\b\d+\s*[hrzespm]{1,6}(?:/\d+\s*[hrzespm]{1,6})?\b",
    re.IGNORECASE,
)


def has_clinical_figures(text):
    """True si el texto contiene dosis, duraciones o pautas (p. ej. "300 mg",
    "6 meses", "2HRZE/4HR", "3HP")."""
    return bool(text and _FIGURE_RE.search(normalize(text)))


def extract_numbers(text):
    """Lista ordenada de las cifras de un texto, con digitos de cualquier
    sistema (arabigos orientales, urdu…) convertidos a 0-9 y coma decimal
    normalizada a punto."""
    if not text:
        return []
    converted = "".join(str(unicodedata.digit(ch)) if ch.isdigit() else ch for ch in text)
    converted = re.sub(r"(?<=\d),(?=\d)", ".", converted)
    return sorted(re.findall(r"\d+(?:\.\d+)?", converted))


def numbers_preserved(original, translated):
    """True si la traduccion contiene exactamente las mismas cifras que el
    original (ni se pierde ni se cambia ninguna dosis, duracion o telefono)."""
    return extract_numbers(original) == extract_numbers(translated)


_NUMBER_WORDS = {
    "1": ["one", "uno", "una", "un"], "2": ["two", "dos"], "3": ["three", "tres"], "4": ["four", "cuatro"],
    "5": ["five", "cinco"], "6": ["six", "seis"], "7": ["seven", "siete"], "8": ["eight", "ocho"],
    "9": ["nine", "nueve"], "10": ["ten", "diez"], "11": ["eleven", "once"], "12": ["twelve", "doce"],
    "15": ["fifteen", "quince"], "18": ["eighteen", "dieciocho"], "20": ["twenty", "veinte"],
    "24": ["twenty-four", "veinticuatro"], "30": ["thirty", "treinta"], "36": ["thirty-six", "treinta y seis"],
}


def figures_supported_by_context(claim, context_text):
    """True si TODAS las cifras de la afirmacion aparecen en el contexto, como
    numero o como palabra en ingles/castellano ("3" ~ "three" ~ "tres").

    Hallazgo de las pruebas en vivo (octubre 2026): el verificador LLM marcaba
    "3 meses" como no respaldado aunque la fuente decia "Three months of
    rifapentine and isoniazid" (las guias de la OMS estan en ingles). Sin esta
    comprobacion se bloqueaban casi todas las respuestas sobre duraciones."""
    numbers = extract_numbers(claim)
    if not numbers:
        return False
    ctx_numbers = set(extract_numbers(context_text))
    ctx = normalize(context_text)
    for n in numbers:
        n_int = n.split(".")[0] if n.endswith(".0") else n
        if n_int in ctx_numbers:
            continue
        if any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", ctx) for w in _NUMBER_WORDS.get(n_int, [])):
            continue
        return False
    return True


# ------------------------------------------------------------------------------
# Citas
# ------------------------------------------------------------------------------
_CITATION_RE = re.compile(r"\(Fuente:\s*([^,)]+?)\s*(?:,\s*p\.?\s*(\d+))?\s*\)", re.IGNORECASE)


def find_invalid_citations(response_text, used_sources):
    """Devuelve las citas "(Fuente: X, p.N)" de la respuesta que no
    corresponden a ninguna de las fuentes usadas para generarla (nombre
    inexistente, o pagina que no estaba en el contexto)."""
    valid = {}
    for s in used_sources:
        valid.setdefault(normalize(str(s.get("source", ""))), set()).add(s.get("page"))
    invalid = []
    for match in _CITATION_RE.finditer(response_text or ""):
        name, page = normalize(match.group(1)), match.group(2)
        pages = next((p for src, p in valid.items() if src and (src in name or name in src)), None)
        if pages is None:
            invalid.append(match.group(0))
        elif page is not None and None not in pages and int(page) not in {int(p) for p in pages if p is not None}:
            invalid.append(match.group(0))
    return invalid
