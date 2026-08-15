path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

anchor = "def detect_generic_knowledge_leak(response_text):"
assert anchor in content, "No se encontro detect_generic_knowledge_leak"

shared_code = '''# FASE 6 (reranking): terminos cortos pero clinicamente importantes que el
# filtro general de "palabras de 4+ letras" excluiria por error (BCG, TB, QT,
# VIH, ITL, TST, PPD, DR, RR son todos acronimos de 2-3 letras habituales en
# tuberculosis).
SHORT_SIGNIFICANT_TERMS = {"bcg", "tb", "qt", "vih", "itl", "tst", "ppd", "dr", "rr", "mdr", "xdr"}

RERANK_POOL_SIZE = 20


def keyword_overlap_score(query, fragment_text):
    query_norm = normalize_accents(query)
    query_words = set(w for w in re.findall(r"[a-z]+", query_norm) if len(w) >= 4)
    query_words |= set(w for w in re.findall(r"[a-z]+", query_norm) if w in SHORT_SIGNIFICANT_TERMS)
    frag_norm = normalize_accents(fragment_text)
    return sum(1 for w in query_words if w in frag_norm)


def rerank_fragments(query, fragments, metadatas, distances, final_k):
    """Reordena los fragmentos recuperados combinando distancia vectorial
    con solapamiento de palabras clave, y devuelve solo los final_k mejores.
    IMPORTANTE: esta funcion NO debe usarse para decidir si hay informacion
    suficiente (eso sigue basandose en distances[0] del orden vectorial
    original, sin reordenar, para no reabrir el riesgo de alucinacion visto
    en pruebas anteriores con top_k alto)."""
    scored = []
    for frag, meta, dist in zip(fragments, metadatas, distances):
        kw_score = keyword_overlap_score(query, frag)
        adjusted_distance = dist - (kw_score * 40)
        scored.append((frag, meta, adjusted_distance))
    scored.sort(key=lambda x: x[2])
    top = scored[:final_k]
    return [t[0] for t in top], [t[1] for t in top]


def detect_generic_knowledge_leak(response_text):'''

content = content.replace(anchor, shared_code, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Funciones de reranking anadidas a nivel de modulo")
