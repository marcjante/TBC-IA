#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige un hallazgo real de Fase 4 (suficiencia y abstencion) encontrado
el 23 de agosto de 2026 al revisar hybrid_retrieve() con calma:

1. El valor centinela para fuentes encontradas SOLO por BM25 (sin
   coincidencia semantica real) era igual al umbral estricto
   (STRICT_DISTANCE_THRESHOLD) — lo que significa que esas fuentes
   siempre "pasaban" el filtro de relevancia, aunque no fueran realmente
   relevantes por significado. Se cambia a un valor claramente malo
   (999999) que nunca satisface ningun umbral por si solo.

2. is_relevant() solo miraba distances[0] (la primera fuente de la
   lista fusionada por RRF). Con fusion hibrida, el orden prioriza una
   mezcla de señales, no solo la confianza semantica pura — la fuente
   con mejor distancia real puede no ir primera. Se cambia a mirar la
   MEJOR distancia entre todas las fuentes devueltas (min), no solo la
   primera posicion.

Con ambos cambios: una pregunta solo se considera "con evidencia
suficiente" si de verdad existe al menos una fuente con una distancia
semantica real (no centinela) dentro del umbral aplicable — no porque
BM25 encontrara una coincidencia de palabras sin relacion semantica de
fondo, ni por casualidad de posicion en la lista fusionada.

Uso:
    python3 fix_hybrid_sufficiency.py "/ruta/a/backend/rag.py"
"""

import sys

OLD_1 = '''        elif doc_id in bm25_lookup:
            doc, meta = bm25_lookup[doc_id]
            dist = STRICT_DISTANCE_THRESHOLD'''

NEW_1 = '''        elif doc_id in bm25_lookup:
            doc, meta = bm25_lookup[doc_id]
            # Valor centinela deliberadamente MALO (no el umbral estricto):
            # una fuente encontrada solo por BM25 (palabras exactas) no
            # tiene garantia de relacion semantica real, asi que no debe
            # poder "pasar" el filtro de relevancia por si sola.
            dist = 999999'''

OLD_2 = '''def is_relevant(fragments, distances, has_keyword):
    """Aplica el filtro de doble umbral: si la pregunta contiene una palabra
    clave relacionada con tuberculosis, se usa el umbral permisivo (750);
    si no, el estricto (480). Devuelve False si no hay fragmentos o si la
    distancia del mejor resultado supera el umbral aplicable."""
    if not fragments or not distances:
        return False
    threshold = LOOSE_DISTANCE_THRESHOLD if has_keyword else STRICT_DISTANCE_THRESHOLD
    return distances[0] <= threshold'''

NEW_2 = '''def is_relevant(fragments, distances, has_keyword):
    """Aplica el filtro de doble umbral: si la pregunta contiene una palabra
    clave relacionada con tuberculosis, se usa el umbral permisivo (750);
    si no, el estricto (480). Devuelve False si no hay fragmentos o si
    NINGUNA fuente devuelta tiene una distancia dentro del umbral
    aplicable.

    Se comprueba la MEJOR distancia de toda la lista (min), no solo la
    primera posicion: con retrieval hibrido (RRF) el orden prioriza una
    mezcla de señales de BM25 y densidad semantica, asi que la fuente
    con mejor confianza semantica real no siempre va primera. Corregido
    el 23 de agosto de 2026 tras detectar que solo mirar distances[0]
    podia dar un "no relevante" incorrecto cuando la mejor fuente real
    quedaba en segunda posicion o mas abajo."""
    if not fragments or not distances:
        return False
    threshold = LOOSE_DISTANCE_THRESHOLD if has_keyword else STRICT_DISTANCE_THRESHOLD
    return min(distances) <= threshold'''


def apply_patch(path, old, new, label):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if new in content:
        print(f"  {label}: ya estaba aplicado (no se ha tocado nada).")
        return content, False

    count = content.count(old)
    if count == 0:
        print(f"  {label}: ABORTADO, no se encontró el bloque esperado. No se ha escrito nada de este paso.")
        return content, False
    if count > 1:
        print(f"  {label}: ABORTADO, el bloque aparece {count} veces (debería ser único). No se ha escrito nada de este paso.")
        return content, False

    content = content.replace(old, new, 1)
    print(f"  {label}: aplicado correctamente.")
    return content, True


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 fix_hybrid_sufficiency.py <ruta a backend/rag.py>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()

    for old, new, label in [
        (OLD_1, NEW_1, "sentinela de distancia BM25-only"),
        (OLD_2, NEW_2, "is_relevant (min en vez de posicion 0)"),
    ]:
        content, _ = apply_patch(path, old, new, label)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
