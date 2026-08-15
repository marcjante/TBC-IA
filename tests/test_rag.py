"""
TBC-AI - tests/test_rag.py

Tests unitarios para backend/rag.py: fragmentacion de texto (chunk_text,
chunk_id) y logica del filtro de doble umbral (is_relevant).

NOTA: importar backend.rag inicializa un ChromaDB PersistentClient sobre
vector_db/ (a traves de backend.config). No hace falta que Ollama este
corriendo para estos tests -- ninguna de las funciones probadas aqui llama
a Ollama ni hace peticiones de red.

FASE 8 de la auditoria.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag import chunk_text, chunk_id, is_relevant, STRICT_DISTANCE_THRESHOLD, LOOSE_DISTANCE_THRESHOLD


class TestChunkText:
    def test_texto_corto_sin_suficientes_alfanumericos_se_descarta(self):
        # Menos de MIN_ALNUM_CHARS (40) caracteres alfanumericos reales:
        # ruido tipico de tablas/paginacion que no aporta contenido.
        texto_corto = "12 34 --- ... . . ."
        assert chunk_text(texto_corto) == []

    def test_texto_con_contenido_real_se_conserva(self):
        texto = "La tuberculosis es una enfermedad infecciosa causada por Mycobacterium tuberculosis, que afecta principalmente a los pulmones."
        chunks = chunk_text(texto)
        assert len(chunks) == 1
        assert chunks[0] == texto

    def test_texto_largo_se_divide_en_varios_fragmentos(self):
        # Texto mayor que CHUNK_SIZE (2000) debe producir mas de un fragmento.
        texto_largo = "La tuberculosis es una enfermedad grave. " * 100  # ~4200 caracteres
        chunks = chunk_text(texto_largo)
        assert len(chunks) > 1

    def test_fragmentos_no_estan_vacios(self):
        texto_largo = "Informacion clinica relevante sobre tuberculosis y su tratamiento adecuado. " * 50
        chunks = chunk_text(texto_largo)
        for c in chunks:
            assert len(c.strip()) > 0

    def test_texto_vacio_no_produce_fragmentos(self):
        assert chunk_text("") == []


class TestChunkId:
    def test_mismos_inputs_producen_mismo_id(self):
        id1 = chunk_id("guia.pdf", 5, 0)
        id2 = chunk_id("guia.pdf", 5, 0)
        assert id1 == id2

    def test_inputs_distintos_producen_ids_distintos(self):
        id1 = chunk_id("guia.pdf", 5, 0)
        id2 = chunk_id("guia.pdf", 5, 1)
        id3 = chunk_id("guia.pdf", 6, 0)
        id4 = chunk_id("otra_guia.pdf", 5, 0)
        assert len({id1, id2, id3, id4}) == 4

    def test_id_es_string_no_vacio(self):
        cid = chunk_id("guia.pdf", 1, 0)
        assert isinstance(cid, str)
        assert len(cid) > 0


class TestIsRelevant:
    def test_sin_fragmentos_no_es_relevante(self):
        assert is_relevant([], [], has_keyword=True) is False

    def test_sin_distancias_no_es_relevante(self):
        assert is_relevant(["algun texto"], [], has_keyword=True) is False

    def test_con_keyword_dentro_del_umbral_permisivo(self):
        distancia = LOOSE_DISTANCE_THRESHOLD - 10
        assert is_relevant(["frag"], [distancia], has_keyword=True) is True

    def test_con_keyword_fuera_del_umbral_permisivo(self):
        distancia = LOOSE_DISTANCE_THRESHOLD + 10
        assert is_relevant(["frag"], [distancia], has_keyword=True) is False

    def test_sin_keyword_dentro_del_umbral_estricto(self):
        distancia = STRICT_DISTANCE_THRESHOLD - 10
        assert is_relevant(["frag"], [distancia], has_keyword=False) is True

    def test_sin_keyword_fuera_del_umbral_estricto(self):
        distancia = STRICT_DISTANCE_THRESHOLD + 10
        assert is_relevant(["frag"], [distancia], has_keyword=False) is False

    def test_caso_critico_entre_umbrales_sin_keyword_debe_fallar(self):
        # Este es el caso de seguridad mas importante: una distancia entre
        # el umbral estricto y el permisivo SOLO debe considerarse relevante
        # si hay palabra clave. Sin keyword, debe rechazarse aunque este
        # dentro del umbral permisivo -- es la logica que evita que
        # preguntas genericas ("hola como estas") cuelen contenido con
        # distancia media-alta.
        distancia_intermedia = (STRICT_DISTANCE_THRESHOLD + LOOSE_DISTANCE_THRESHOLD) / 2
        assert is_relevant(["frag"], [distancia_intermedia], has_keyword=False) is False
        assert is_relevant(["frag"], [distancia_intermedia], has_keyword=True) is True

    def test_umbrales_no_han_cambiado_de_valor(self):
        # Guarda de regresion: si alguien cambia estos valores sin darse
        # cuenta del impacto (ver Fase 6, hallazgo sobre top_k y riesgo de
        # alucinacion), este test lo señala explicitamente.
        assert STRICT_DISTANCE_THRESHOLD == 480
        assert LOOSE_DISTANCE_THRESHOLD == 750
