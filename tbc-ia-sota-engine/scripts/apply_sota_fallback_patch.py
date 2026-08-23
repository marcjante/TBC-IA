#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplica a backend/main.py los cambios necesarios para integrar
query_sota_fallback() en /api/chat y /api/patient-chat.

Es idempotente y seguro: si algún bloque de texto esperado no se encuentra
tal cual (por ejemplo porque ya se aplicó antes, o el archivo es distinto
de lo esperado), se aborta sin escribir nada. No deja el archivo a medias.

Uso:
    python3 scripts/apply_sota_fallback_patch.py "/Users/marcjantecastellvi/Desktop/TBC IA/backend/main.py"
"""

import sys

FINAL_IMPORT = "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback, verify_groundedness\nfrom backend.llm import generate_response"

# Variantes posibles del import segun el estado previo del archivo, en orden
# de comprobacion. Se ancla con el import siguiente ("\\nfrom backend.llm...")
# para que el texto original de 3 nombres no coincida por accidente como
# subcadena del ya parcheado de 4 nombres (ambos empiezan igual, por eso no
# basta con buscar solo el principio de la linea).
IMPORT_VARIANTS = [
    "from backend.rag import retrieve, is_relevant, index_single_pdf, query_sota_fallback\nfrom backend.llm import generate_response",
    "from backend.rag import retrieve, is_relevant, index_single_pdf\nfrom backend.llm import generate_response",
]


def apply_import_patch(content):
    """Devuelve (content_actualizado, aplicado: bool, error: str|None)."""
    if FINAL_IMPORT in content:
        return content, False, None  # ya estaba
    for variant in IMPORT_VARIANTS:
        count = content.count(variant)
        if count == 1:
            return content.replace(variant, FINAL_IMPORT, 1), True, None
        if count > 1:
            return content, False, f"el import aparece {count} veces, debería ser único"
    return content, False, "no se encontró ninguna variante conocida del import de backend.rag"


BARE_UPLOAD_ANCHOR = '''    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)

    return result


@app.post("/api/upload")'''

OLD_GROUNDEDNESS_ONLY = '''    if request.debug and sources_used:
        groundedness = verify_groundedness(
            final_response,
            [s["text"] for s in sources_used],
        )
        if groundedness is not None:
            result.setdefault("debug_info", {})["groundedness"] = groundedness

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)

    return result


@app.post("/api/upload")'''

FINAL_GROUNDEDNESS_LLM = '''    if request.debug and sources_used:
        groundedness = verify_groundedness(
            final_response,
            [s["text"] for s in sources_used],
        )
        if groundedness is not None:
            result.setdefault("debug_info", {})["groundedness"] = groundedness

        llm_unsupported_claims = verify_claims_with_llm(
            [s["text"] for s in sources_used],
            final_response,
        )
        if llm_unsupported_claims is not None:
            result.setdefault("debug_info", {})["llm_unsupported_claims"] = llm_unsupported_claims

    log_usage_pattern("/api/chat", result.get("coverage"), question=request.message)

    return result


@app.post("/api/upload")'''


def apply_groundedness_llm_patch(content):
    """Igual que apply_import_patch: el texto de este bloque tiene varios
    estados posibles segun se haya aplicado antes solo groundedness (sesion
    de hoy, primera pasada) o nada en absoluto. Se maneja aparte del bucle
    generico porque BARE_UPLOAD_ANCHOR es literalmente un sufijo de
    OLD_GROUNDEDNESS_ONLY y de FINAL_GROUNDEDNESS_LLM: si se tratara como
    una sustitucion mas de la lista generica, seguiria "encontrandose"
    despues de aplicada y se duplicaria el bloque en cada ejecucion."""
    if FINAL_GROUNDEDNESS_LLM in content:
        return content, False, None  # ya estaba completo
    if OLD_GROUNDEDNESS_ONLY in content:
        count = content.count(OLD_GROUNDEDNESS_ONLY)
        if count == 1:
            return content.replace(OLD_GROUNDEDNESS_ONLY, FINAL_GROUNDEDNESS_LLM, 1), True, None
        return content, False, f"el bloque intermedio (solo groundedness) aparece {count} veces, debería ser único"
    if BARE_UPLOAD_ANCHOR in content:
        count = content.count(BARE_UPLOAD_ANCHOR)
        if count == 1:
            return content.replace(BARE_UPLOAD_ANCHOR, FINAL_GROUNDEDNESS_LLM, 1), True, None
        return content, False, f"el ancla original aparece {count} veces, debería ser único"
    return content, False, "no se encontró ninguna variante conocida del bloque de groundedness/LLM"


REPLACEMENTS = [
    # 1. Bloque de "no relevante" en /api/chat
    (
'''    if not is_relevant(fragments, distances, has_keyword):
        log_usage_pattern("/api/chat", "sin_cobertura", question=request.message)
        return {
            "response": "No encuentro esta informacion en los documentos disponibles.",
            "sources": [],
        }''',
'''    fallback_used = False
    if not is_relevant(fragments, distances, has_keyword):
        fb_fragments, fb_metadatas, fb_info = query_sota_fallback(retrieval_query)

        if fb_info and isinstance(fb_info, dict) and fb_info.get("alert"):
            log_usage_pattern("/api/chat", "alerta_clinica", question=request.message)
            return {
                "response": " ".join(fb_info["alert"]),
                "sources": [],
                "coverage": "alerta_clinica",
            }

        if fb_fragments:
            fragments, metadatas = fb_fragments, fb_metadatas
            distances = []
            fallback_used = True
        else:
            log_usage_pattern("/api/chat", "sin_cobertura", question=request.message)
            return {
                "response": "No encuentro esta informacion en los documentos disponibles.",
                "sources": [],
            }''',
    ),
    # 2. Bucle de construccion de contexto/fuentes en /api/chat (soporta page=None)
    (
'''    for frag, meta in zip(fragments, metadatas):
        context_parts.append(
            "[Fuente: " + meta["source"] + ", categoria: " + meta["category"] + ", pagina: " + str(meta["page"]) + "]\\n" + frag
        )
        sources_used.append({
            "source": meta["source"],
            "category": meta["category"],
            "page": meta["page"],
            "text": frag,
        })''',
'''    for frag, meta in zip(fragments, metadatas):
        page_part = ", pagina: " + str(meta["page"]) if meta.get("page") is not None else ""
        context_parts.append(
            "[Fuente: " + meta["source"] + ", categoria: " + meta["category"] + page_part + "]\\n" + frag
        )
        sources_used.append({
            "source": meta["source"],
            "category": meta["category"],
            "page": meta.get("page"),
            "text": frag,
        })''',
    ),
    # 3. Calculo de coverage en /api/chat: anteponer caso "complementaria"
    (
'''    if distances and sources_used:
        best_distance = distances[0]
        if best_distance <= 400:
            result["coverage"] = "alta"
        elif best_distance <= 600:
            result["coverage"] = "media"
        else:
            result["coverage"] = "baja"
    else:
        result["coverage"] = None''',
'''    if fallback_used and sources_used:
        result["coverage"] = "complementaria"
    elif distances and sources_used:
        best_distance = distances[0]
        if best_distance <= 400:
            result["coverage"] = "alta"
        elif best_distance <= 600:
            result["coverage"] = "media"
        else:
            result["coverage"] = "baja"
    else:
        result["coverage"] = None''',
    ),
    # 4. Bloque de "no relevante" en /api/patient-chat
    (
'''    if not is_relevant(fragments, distances, has_keyword):
        log_usage_pattern("/api/patient-chat", "sin_cobertura", lang=request.lang)
        return {"response": canned_no_info}''',
'''    fallback_used = False
    if not is_relevant(fragments, distances, has_keyword):
        fb_fragments, fb_metadatas, fb_info = query_sota_fallback(retrieval_query)

        if fb_info and isinstance(fb_info, dict) and fb_info.get("alert"):
            log_usage_pattern("/api/patient-chat", "alerta_clinica", lang=request.lang)
            alert_text = " ".join(fb_info["alert"])
            return {"response": f"{alert_text} {canned_no_info}"}

        if fb_fragments:
            fragments, metadatas = fb_fragments, fb_metadatas
            distances = []
            fallback_used = True
        else:
            log_usage_pattern("/api/patient-chat", "sin_cobertura", lang=request.lang)
            return {"response": canned_no_info}''',
    ),
    # 5. Calculo de internal_coverage en /api/patient-chat: anteponer "complementaria"
    (
'''    if distances:
        best_distance = distances[0]
        if best_distance <= 400:
            internal_coverage = "alta"
        elif best_distance <= 600:
            internal_coverage = "media"
        else:
            internal_coverage = "baja"
    else:
        internal_coverage = None''',
'''    if fallback_used:
        internal_coverage = "complementaria"
    elif distances:
        best_distance = distances[0]
        if best_distance <= 400:
            internal_coverage = "alta"
        elif best_distance <= 600:
            internal_coverage = "media"
        else:
            internal_coverage = "baja"
    else:
        internal_coverage = None''',
    ),
    # 7. debug_info en /api/chat: anadir fallback_used
    (
'''    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": request.top_k,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fragments_retrieved": len(fragments),
        }''',
'''    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": request.top_k,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fragments_retrieved": len(fragments),
            "fallback_used": fallback_used,
        }''',
    ),
    # 8. debug_info en /api/patient-chat: anadir fallback_used
    (
'''    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": 8,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
        }''',
'''    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": 8,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fallback_used": fallback_used,
        }''',
    ),
    # 9. Insertar funciones de verificacion via LLM (segunda pasada), justo
    # despues del middleware CORS, antes de los modelos Pydantic.
    (
'''app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)''',
'''app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    match = re.search(r"\\{.*\\}", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            claims = parsed.get("unsupported_claims", [])
            return claims if isinstance(claims, list) else None
        except (json.JSONDecodeError, AttributeError):
            return None
    return None


def verify_claims_with_llm(sources_texts, response_text):
    """Pide al propio LLM (via generate_response, ya usado en el resto de
    TBC-AI) que revise la respuesta ya generada contra las fuentes, en una
    llamada aparte. NO decide nada sobre la respuesta: solo informa.
    Devuelve None si falla cualquier paso (fail-open, no bloquea el flujo
    normal por un fallo de esta verificacion adicional)."""
    if not sources_texts:
        return None
    context_text = "\\n\\n---\\n\\n".join(sources_texts)
    user_msg = f"CONTEXTO:\\n{context_text}\\n\\nRESPUESTA A REVISAR:\\n{response_text}"
    try:
        raw = generate_response(VERIFICATION_SYSTEM_PROMPT, user_msg)
    except Exception:
        return None
    return parse_verification_response(raw)''',
    ),
]


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 apply_sota_fallback_patch.py <ruta a backend/main.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    already_patched_markers = ["query_sota_fallback(retrieval_query)", "fallback_used = False"]
    already_done = sum(1 for m in already_patched_markers if m in content)

    applied = []
    skipped_already_done = []
    errors = []

    content, import_applied, import_error = apply_import_patch(content)
    if import_error:
        errors.append(f"Import: {import_error}")
    elif import_applied:
        applied.append("import")
    else:
        skipped_already_done.append("import")

    content, gr_applied, gr_error = apply_groundedness_llm_patch(content)
    if gr_error:
        errors.append(f"Groundedness/LLM: {gr_error}")
    elif gr_applied:
        applied.append("groundedness_llm")
    else:
        skipped_already_done.append("groundedness_llm")

    for i, (old, new) in enumerate(REPLACEMENTS, start=1):
        if new in content:
            skipped_already_done.append(i)
            continue
        count = content.count(old)
        if count == 0:
            errors.append(f"Cambio {i}: no se encontró el texto esperado (¿ya aplicado con otra redacción, o archivo distinto?)")
            continue
        if count > 1:
            errors.append(f"Cambio {i}: el texto esperado aparece {count} veces (debería ser único). Abortando por seguridad.")
            continue
        content = content.replace(old, new, 1)
        applied.append(i)

    if errors:
        print("ABORTADO. No se ha escrito nada en el archivo. Problemas encontrados:")
        for e in errors:
            print(" -", e)
        print("\nRevisa manualmente esos puntos antes de reintentar.")
        sys.exit(1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Cambios aplicados: {applied}")
    if skipped_already_done:
        print(f"Cambios ya presentes (no tocados): {skipped_already_done}")
    print(f"Archivo actualizado: {path}")


if __name__ == "__main__":
    main()
