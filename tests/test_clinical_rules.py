"""
TBC-AI - tests/test_clinical_rules.py

Reglas clinicas deterministas de backend/clinical_rules.py (revision de
seguridad clinica, octubre 2026). No requieren Ollama ni ChromaDB.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.clinical_rules import (
    check_red_flags, interaction_warnings, population_caveat, has_clinical_figures,
    extract_numbers, numbers_preserved, find_invalid_citations, normalize, figures_supported_by_context,
)
from backend.safety import is_tb_related


class TestRedFlags:
    def test_nuevos_signos_de_alarma(self):
        casos = {
            "Me falta el aire desde esta mañana": "respiratory_distress",
            "tengo un dolor en el pecho muy fuerte": "chest_pain",
            "me han salido ampollas en la piel": "severe_skin_or_allergic_reaction",
            "no paro de vomitar desde ayer": "persistent_vomiting_or_abdominal_pain",
            "mi madre esta confundida y desorientada": "neurological",
            "llevo tres dias con fiebre alta": "high_persistent_fever",
        }
        for mensaje, regla in casos.items():
            assert check_red_flags(mensaje) == regla, mensaje

    def test_vision_borrosa_sin_nombrar_el_farmaco(self):
        # Antes hacia falta escribir "etambutol" para que saltara la alerta.
        assert check_red_flags("desde que tomo las pastillas veo borroso") == "visual_toxicity"

    def test_tildes_no_impiden_la_deteccion(self):
        assert check_red_flags("Tengo DISNEA y dolor torácico") is not None
        assert check_red_flags("me desmayé en la calle") == "syncope_cardiac"

    def test_catalan_basico(self):
        assert check_red_flags("tinc tos amb sang") == "hemoptysis"
        assert check_red_flags("m'ofego quan camino") == "respiratory_distress"

    def test_consulta_normal_no_salta(self):
        assert check_red_flags("cuanto dura el tratamiento de la tuberculosis latente") is None
        assert check_red_flags("puedo tomar cafe con la medicacion") is None

    def test_varios_textos_original_y_traduccion(self):
        assert check_red_flags("texto en otro idioma", "tengo tos con sangre") == "hemoptysis"


class TestInteracciones:
    def test_anticonceptivos(self):
        avisos = interaction_warnings("tomo rifampicina, ¿afecta a la píldora anticonceptiva?")
        assert any("anticonceptivos hormonales" in a for a in avisos)

    def test_sintrom(self):
        assert any("anticoagulantes" in a for a in interaction_warnings("estoy con Sintrom"))

    def test_metadona_y_vih(self):
        avisos = interaction_warnings("tomo metadona y tengo VIH")
        assert len(avisos) == 2

    def test_piridoxina_con_isoniazida_en_embarazo(self):
        avisos = interaction_warnings("estoy embarazada y me han dado isoniazida")
        assert any("piridoxina" in a for a in avisos)

    def test_sin_interacciones(self):
        assert interaction_warnings("cuanto dura el tratamiento") == []


class TestPoblaciones:
    def test_nino_con_cifras(self):
        aviso = population_caveat("cuanto dura el tratamiento en mi hijo", "La pauta dura 6 meses.")
        assert aviso and "niños" in aviso

    def test_sin_cifras_no_hay_aviso(self):
        assert population_caveat("tratamiento en embarazo", "Consulta a tu equipo.") is None

    def test_adulto_sin_poblacion_especial(self):
        assert population_caveat("cuanto dura el tratamiento", "Dura 6 meses.") is None


class TestCifras:
    def test_detecta_dosis_duraciones_y_pautas(self):
        for texto in ["300 mg al dia", "durante 6 meses", "la pauta 2HRZE/4HR", "el regimen 3HP", "10 mg/kg"]:
            assert has_clinical_figures(texto), texto

    def test_texto_sin_cifras(self):
        assert not has_clinical_figures("Habla con tu equipo de tratamiento.")

    def test_extract_numbers_digitos_arabes_orientales(self):
        assert extract_numbers("خذ ٣٠٠ ملغ لمدة ٦ أشهر") == ["300", "6"]

    def test_traduccion_que_conserva_cifras(self):
        assert numbers_preserved("Toma 300 mg durante 6 meses. Llama al 112.",
                                 "Pren 300 mg durant 6 mesos. Truca al 112.")

    def test_traduccion_que_cambia_una_dosis(self):
        assert not numbers_preserved("Toma 300 mg durante 6 meses.", "Pren 30 mg durant 6 mesos.")

    def test_traduccion_que_pierde_una_cifra(self):
        assert not numbers_preserved("Durante 6 meses, 300 mg.", "Durant uns mesos, 300 mg.")


class TestCitas:
    fuentes = [{"source": "WHO_guidelines_2022.pdf", "page": 12}, {"source": "CDC_LTBI.pdf", "page": 3}]

    def test_citas_validas(self):
        texto = "Dura 6 meses (Fuente: WHO_guidelines_2022.pdf, p.12)."
        assert find_invalid_citations(texto, self.fuentes) == []

    def test_fuente_inventada(self):
        texto = "Dura 4 meses (Fuente: NICE_2019.pdf, p.40)."
        assert find_invalid_citations(texto, self.fuentes) == ["(Fuente: NICE_2019.pdf, p.40)"]

    def test_pagina_que_no_estaba_en_el_contexto(self):
        texto = "Dura 6 meses (Fuente: CDC_LTBI.pdf, p.99)."
        assert len(find_invalid_citations(texto, self.fuentes)) == 1


class TestRelevanciaPorPalabra:
    def test_tos_no_coincide_con_datos(self):
        assert is_tb_related("me faltan datos") is False

    def test_raices_siguen_funcionando(self):
        assert is_tb_related("tengo vomitos") is True
        assert is_tb_related("tuberculosis pulmonar") is True


def test_normalize():
    assert normalize("  Tórax   ÁCIDO ") == "torax acido"


class TestCifrasEnContexto:
    def test_cifra_en_palabras_inglesas(self):
        assert figures_supported_by_context("3 meses", "Three months of rifapentine and isoniazid (3HP)")

    def test_cifra_en_digitos(self):
        assert figures_supported_by_context("dura 12 semanas", "3HP is given once weekly for 12 weeks")

    def test_cifra_inventada(self):
        assert not figures_supported_by_context("dura 9 meses", "Three months of rifapentine and isoniazid")

    def test_dosis_cambiada(self):
        assert not figures_supported_by_context("900 mg de isoniazida", "isoniazid 300 mg daily")
