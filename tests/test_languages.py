"""
TBC-AI - tests/test_languages.py

Tests unitarios para backend/languages.py: resolucion de nombre de idioma
y mensaje fijo de "sin informacion" para cada uno de los 4 idiomas
soportados.

FASE 8 de la auditoria.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.languages import resolve_lang_name, resolve_canned_no_info, LANG_NAMES, CANNED_NO_INFO_BY_LANG


class TestResolveLangName:
    def test_castellano(self):
        assert resolve_lang_name("es") == "castellano"

    def test_catalan(self):
        assert resolve_lang_name("ca") == "catalan"

    def test_arabe_menciona_darija(self):
        # El nombre de idioma para arabe debe seguir indicando explicitamente
        # que se usa fusha/estandar por motivos de seguridad de traduccion
        # (ver README.md, seccion 10.5.1).
        assert "darija" in resolve_lang_name("ar")

    def test_urdu(self):
        assert resolve_lang_name("ur") == "urdu"

    def test_codigo_desconocido_cae_a_castellano(self):
        assert resolve_lang_name("xx") == "castellano"
        assert resolve_lang_name("") == "castellano"


class TestResolveCannedNoInfo:
    def test_los_4_idiomas_tienen_mensaje_propio(self):
        for lang in ("es", "ca", "ar", "ur"):
            msg = resolve_canned_no_info(lang)
            assert isinstance(msg, str)
            assert len(msg) > 0

    def test_codigo_desconocido_cae_a_castellano(self):
        assert resolve_canned_no_info("xx") == CANNED_NO_INFO_BY_LANG["es"]

    def test_mensajes_son_todos_distintos_entre_si(self):
        # Si dos idiomas comparten exactamente el mismo texto por error de
        # copia/pega, esto lo detectaria (salvo que sea intencional).
        mensajes = [resolve_canned_no_info(l) for l in ("es", "ca", "ar", "ur")]
        assert len(mensajes) == len(set(mensajes))

    def test_todos_los_codigos_de_lang_names_tienen_mensaje(self):
        # Consistencia entre los dos diccionarios: todo idioma soportado
        # para el prompt debe tener tambien su mensaje de "sin informacion".
        for lang_code in LANG_NAMES:
            assert lang_code in CANNED_NO_INFO_BY_LANG
