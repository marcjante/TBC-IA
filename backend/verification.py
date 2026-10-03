"""
TBC-AI - backend/verification.py

Segunda pasada de verificacion de la respuesta generada (extraido de main.py
en la revision de seguridad clinica de octubre 2026):
- verify_claims_with_llm(): el propio LLM marca afirmaciones no respaldadas
  por el contexto.
- compare_with_llamafile(): comparacion con un segundo modelo (solo debug).

Cambios de la revision: logging en vez de print (no se vuelcan contextos ni
salidas crudas en los logs) y el verificador ve el MISMO contexto que vio el
generador (A1/A7), con un limite mas amplio.
"""

import json
import logging
import re

from backend.llm import generate_response

logger = logging.getLogger("tbc.verification")


# ==============================================================================
# VERIFICACION DE AFIRMACIONES VIA LLM (segunda pasada) - agosto 2026
# ==============================================================================
# Alternativa/complemento al chequeo NLI de verify_groundedness() en rag.py:
# el modelo NLI generico no distingue bien sustituciones finas de un termino
# concreto por otro con la misma plantilla de frase (ej. "ansiedad" -> "soledad"
# manteniendo "es un sintoma comun de tuberculosis"). Se le pide al propio LLM
# que revise sus afirmaciones contra el contexto, en una llamada aparte.
# Solo informativo (debug_info), no altera la respuesta real al paciente.

VERIFICATION_SYSTEM_PROMPT = """Eres un revisor clinico. Se te da un CONTEXTO (fragmentos de fuentes documentales) y una RESPUESTA que otro asistente genero a partir de ese contexto para un paciente o profesional.

Tu tarea: identifica frases de la RESPUESTA que afirman algo clinico o factual concreto que NO esta respaldado, ni literalmente ni por una inferencia razonable, en el CONTEXTO. El asistente que genero la respuesta a veces "rellena" con afirmaciones inventadas que sustituyen un termino del contexto por otro parecido (por ejemplo, el contexto habla de ansiedad y la respuesta afirma algo especifico sobre soledad, sin que el contexto lo respalde).

NO marques:
- Frases genericas de acompanamiento ("habla con tu equipo medico", "no estas solo en esto").
- Reformulaciones fieles del contexto, aunque cambien las palabras.
- Recomendaciones de sentido comun no especificas (respirar hondo, hablar con alguien de confianza).

SI marca:
- Afirmaciones especificas sobre sintomas, causas, pronosticos, o tratamientos que no aparecen en el contexto.

Responde EXCLUSIVAMENTE con un JSON con este formato exacto, sin texto antes ni despues:
{"unsupported_claims": ["frase exacta 1", "frase exacta 2"]}

Si todas las frases estan respaldadas, responde exactamente:
{"unsupported_claims": []}
"""


def parse_verification_response(raw):
    """Extrae la lista unsupported_claims del texto devuelto por el LLM,
    tolerando que venga envuelto en bloques de codigo o con texto alrededor
    (Llama a veces no sigue la instruccion de "solo JSON" al pie de la letra).
    Devuelve None si no se puede interpretar nada (fail-open)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        claims = parsed.get("unsupported_claims", [])
        return claims if isinstance(claims, list) else None
    except (json.JSONDecodeError, AttributeError):
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            claims = parsed.get("unsupported_claims", [])
            return claims if isinstance(claims, list) else None
        except (json.JSONDecodeError, AttributeError):
            return None
    return None


def normalize_text_for_claim_check(text):
    text = text.lower()
    for a, b in [("\u00e1", "a"), ("\u00e9", "e"), ("\u00ed", "i"), ("\u00f3", "o"), ("\u00fa", "u"), ("\u00f1", "n")]:
        text = text.replace(a, b)
    text = re.sub(r"[^\w\s]", " ", text)
    return text


def claim_actually_in_response(claim, response_text, threshold=0.5):
    """Comprueba que una afirmacion marcada por el verificador realmente
    aparece (por solapamiento de palabras) en el texto de la respuesta
    revisada. Descubierto en pruebas (agosto 2026): el propio LLM
    verificador puede marcar una frase que ni siquiera esta en el texto
    original — una alucinacion del verificador, no una deteccion real."""
    claim_words = set(normalize_text_for_claim_check(claim).split())
    if not claim_words:
        return False
    response_words = set(normalize_text_for_claim_check(response_text).split())
    overlap = len(claim_words & response_words) / len(claim_words)
    return overlap >= threshold


def verify_claims_with_llm(sources_texts, response_text):
    """Pide al propio LLM (via generate_response, ya usado en el resto de
    TBC-AI) que revise la respuesta ya generada contra las fuentes, en una
    llamada aparte. NO decide nada sobre la respuesta: solo informa.
    Devuelve None si falla cualquier paso (fail-open, no bloquea el flujo
    normal por un fallo de esta verificacion adicional).

    Filtra ademas las afirmaciones marcadas que no aparecen realmente en
    response_text (alucinaciones del propio verificador, ver
    claim_actually_in_response)."""
    if not sources_texts:
        return None

    # Limitar el tamaño del contexto que ve el VERIFICADOR (no afecta al
    # contexto usado para generar la respuesta real, solo a esta segunda
    # llamada de revision). Con contextos muy largos (muchas fuentes) el
    # verificador puede "distraerse" y responder una pregunta que aparece
    # dentro de las fuentes en vez de hacer la comparacion pedida —
    # detectado en pruebas reales el 22 de agosto de 2026 con 10 fuentes.
    MAX_VERIFIER_CONTEXT_CHARS = 16000
    context_text = "\n\n---\n\n".join(sources_texts)
    context_for_verifier = context_text
    truncated = False
    if len(context_for_verifier) > MAX_VERIFIER_CONTEXT_CHARS:
        context_for_verifier = context_for_verifier[:MAX_VERIFIER_CONTEXT_CHARS] + "\n\n[...contexto recortado para la verificacion...]"
        truncated = True

    # La instruccion se repite al FINAL, despues del contexto, para
    # anclar mejor la tarea cuando el contexto es largo (evita que el
    # modelo responda a algo que aparece dentro del propio contexto).
    user_msg = (
        f"CONTEXTO:\n{context_for_verifier}\n\nRESPUESTA A REVISAR:\n{response_text}\n\n"
        "Recuerda: tu unica tarea es responder EXCLUSIVAMENTE con el JSON pedido "
        "al principio, comparando la RESPUESTA A REVISAR contra el CONTEXTO. "
        "No respondas ninguna otra pregunta que pueda aparecer mencionada dentro "
        "del CONTEXTO."
    )
    logger.debug("verify_claims_with_llm: %s caracteres de contexto%s, %s fuentes", len(context_for_verifier), " (recortado)" if truncated else "", len(sources_texts))
    try:
        raw = generate_response(VERIFICATION_SYSTEM_PROMPT, user_msg)
    except Exception as e:
        logger.warning("verify_claims_with_llm: fallo del LLM (%s)", type(e).__name__)
        return None
    claims = parse_verification_response(raw)
    if claims is None:
        logger.warning("verify_claims_with_llm: respuesta del verificador no interpretable")
        return None
    return [
        c for c in claims
        if claim_actually_in_response(c, response_text) and not is_generic_advice(c)
    ]


GENERIC_ADVICE_PATTERNS = [
    "mantén un registro de tus síntomas",
    "mantén una buena higiene",
    "sigue las instrucciones de tu médico",
    "sigue las instrucciones de tu equipo",
    "habla con tu equipo de tratamiento",
    "consulta a tu médico",
    "consulta con tu médico",
    "busca atención médica",
    "contacta con tu médico",
    "comunícate con tu médico",
]


def is_generic_advice(claim):
    """Descarta frases que son puro consejo generico de acompañamiento
    (ej. "mantén una buena higiene"), aunque el verificador LLM las haya
    marcado como "no respaldadas" — su propia instruccion ya le pide no
    marcarlas, pero no siempre lo cumple de forma consistente. Solo
    descarta si la frase es CASI ENTERAMENTE el consejo generico (queda
    muy poco texto tras quitarlo); si la frase mezcla el consejo con
    contenido clinico especifico adicional, no se descarta."""
    normalized = re.sub(r"[^\w\s]", "", claim.strip().lower())
    for pattern in GENERIC_ADVICE_PATTERNS:
        pattern_norm = re.sub(r"[^\w\s]", "", pattern)
        if pattern_norm in normalized:
            remainder = normalized.replace(pattern_norm, "", 1).strip()
            if len(remainder) < 20:
                return True
    return False


# ==============================================================================
# CONSENSO ENTRE DOS MODELOS (Ollama + Llamafile/Mistral) - agosto 2026
# ==============================================================================
# Señal secundaria (complementaria a verify_claims_with_llm, que es la
# principal): genera una respuesta independiente con un segundo modelo
# para la misma pregunta y contexto, y compara si coinciden en sus
# afirmaciones. Probado hoy como prototipo en dual_model_check.py: util
# para detectar cuando un modelo añade algo que el otro no dice, pero NO
# sustituye a la verificacion contra fuentes (si los dos modelos comparten
# el mismo sesgo de entrenamiento, pueden fabricar la misma idea sin que
# esto lo note - ver seccion 8.3 del resumen del sistema).

COMPARATOR_SYSTEM_PROMPT = """Se te dan dos respuestas (A y B) generadas por dos modelos distintos a la misma pregunta clinica sobre tuberculosis, a partir del mismo contexto documental.

Identifica afirmaciones clinicas o factuales CONCRETAS que aparecen en una respuesta pero no en la otra (sintomas, causas, tratamientos, pronosticos). No cuentes frases genericas de acompanamiento ("habla con tu equipo medico") ni reformulaciones equivalentes con otras palabras.

Responde EXCLUSIVAMENTE con un JSON con este formato exacto, sin texto antes ni despues:
{"claims_only_in_a": ["..."], "claims_only_in_b": ["..."], "agreement": "alto"|"medio"|"bajo"}

"agreement" = "alto" si no hay afirmaciones discrepantes relevantes; "medio" si hay alguna discrepancia menor; "bajo" si hay afirmaciones claramente contradictorias o solo una de las dos respuestas las menciona."""


def parse_comparator_response(raw):
    """Extrae el JSON del comparador, tolerando bloques de codigo o texto
    alrededor (mismo patron que parse_verification_response)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, AttributeError):
            return None
    return None


def compare_with_llamafile(response_a, response_b):
    """Usa Ollama (via generate_response, ya validado hoy como buen juez)
    para comparar dos respuestas de modelos distintos a la misma pregunta.
    Devuelve None si falla cualquier paso (fail-open)."""
    user_prompt = f"RESPUESTA A:\n{response_a}\n\nRESPUESTA B:\n{response_b}"
    try:
        raw = generate_response(COMPARATOR_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning("compare_with_llamafile: fallo del LLM (%s)", type(e).__name__)
        return None
    parsed = parse_comparator_response(raw)
    if parsed is None:
        logger.warning("compare_with_llamafile: respuesta no interpretable")
    return parsed
