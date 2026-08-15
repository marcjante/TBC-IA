"""
TBC-AI - tests/test_safety.py

Tests unitarios para backend/safety.py: filtro de relevancia por palabra
clave (is_tb_related) y deteccion de fuga de conocimiento general
(detect_generic_knowledge_leak). No requieren Ollama ni ChromaDB activos.

FASE 8 de la auditoria.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.safety import is_tb_related, detect_generic_knowledge_leak, normalize_accents, TB_KEYWORDS


class TestIsTbRelated:
    def test_pregunta_con_keyword_clara(self):
        assert is_tb_related("Que es el IGRA?") is True

    def test_pregunta_generica_sin_keyword(self):
        assert is_tb_related("hola como estas") is False

    def test_keyword_al_final_de_la_frase_sin_espacio(self):
        # Bug historico: la deteccion fallaba si la keyword coincidia justo
        # al final de la frase, sin espacio despues (ver sesion de agosto,
        # caso "Necesito un TAC?").
        assert is_tb_related("Necesito un TAC?") is True

    def test_keyword_con_acento_en_la_pregunta(self):
        assert is_tb_related("Qué es la tuberculosis?") is True

    def test_keyword_corta_bcg(self):
        assert is_tb_related("Que es la BCG?") is True

    def test_no_sensible_a_mayusculas(self):
        assert is_tb_related("QUE ES EL IGRA?") is True

    def test_pregunta_vacia(self):
        assert is_tb_related("") is False

    def test_todas_las_keywords_son_strings_no_vacios(self):
        # Verificacion de integridad de la propia lista, para detectar
        # entradas rotas (None, numeros, strings vacios) si alguien la edita
        # a mano en el futuro.
        assert len(TB_KEYWORDS) > 0
        for kw in TB_KEYWORDS:
            assert isinstance(kw, str)
            assert len(kw.strip()) > 0

    def test_sin_keywords_duplicadas_exactas(self):
        assert len(TB_KEYWORDS) == len(set(TB_KEYWORDS))


class TestNormalizeAccents:
    def test_quita_tildes_comunes(self):
        assert normalize_accents("informaci\u00f3n") == "informacion"
        assert normalize_accents("m\u00e9dico") == "medico"

    def test_texto_sin_acentos_no_cambia(self):
        assert normalize_accents("hola mundo") == "hola mundo"

    def test_convierte_a_minusculas(self):
        assert normalize_accents("HOLA") == "hola"


class TestDetectGenericKnowledgeLeak:
    def test_detecta_frase_de_fuga_conocida(self):
        texto = "El contexto no contiene informacion especifica, sin embargo, puedo ofrecerte informacion general sobre esto."
        assert detect_generic_knowledge_leak(texto) is True

    def test_respuesta_normal_sin_fuga(self):
        texto = "El IGRA es una prueba de sangre que detecta la infeccion por tuberculosis. (Fuente: WHO, p.22)"
        assert detect_generic_knowledge_leak(texto) is False

    def test_deteccion_funciona_con_acentos_en_la_respuesta(self):
        # Bug historico: la comparacion fallaba cuando la respuesta tenia
        # tildes y el patron no (ver sesion de agosto, "informacion" vs
        # "información").
        texto = "Seg\u00fan mi conocimiento, esto es informaci\u00f3n general."
        assert detect_generic_knowledge_leak(texto) is True

    def test_frase_fija_correcta_no_activa_el_guard(self):
        texto = "No encuentro esta informacion en los documentos disponibles."
        assert detect_generic_knowledge_leak(texto) is False
