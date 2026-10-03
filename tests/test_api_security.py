"""
TBC-AI - tests/test_api_security.py

Tests de la revision de seguridad de octubre 2026 sobre la API del backend
(puerto 8001) y el flujo de los dos chats. El LLM, el RAG y el motor SOTA se
sustituyen por dobles de prueba: no hace falta Ollama ni ChromaDB activos.
"""

import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TBC_API_KEY", "clave-de-test")
os.environ["TBC_ADMIN_TOKEN"] = "token-admin-test"

from fastapi.testclient import TestClient  # noqa: E402

import backend.config as config  # noqa: E402
import backend.main as main  # noqa: E402

config.ADMIN_TOKEN = main.ADMIN_TOKEN = "token-admin-test"
HOST = {"Host": "127.0.0.1"}

FRAGMENTO = "El tratamiento de la infeccion tuberculosa latente con 3HP dura 3 meses en adultos."
META = {"source": "WHO_guidelines_2022.pdf", "category": "01_WHO", "page": 12}


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Cliente con RAG/LLM/SOTA simulados y registro de uso en un fichero temporal."""
    monkeypatch.setattr(main, "USAGE_LOG_PATH", str(tmp_path / "usage.jsonl"))
    monkeypatch.setattr(main, "DOCUMENTS_DIR", str(tmp_path / "documents"))
    monkeypatch.setattr(main, "classify_intent", lambda m: ("consulta_clinica", True))
    monkeypatch.setattr(main, "expand_query", lambda q: q)
    monkeypatch.setattr(main, "hybrid_retrieve", lambda q, k: ([FRAGMENTO], [META], [300.0]))
    monkeypatch.setattr(main, "query_sota_alerts", lambda q: [])
    monkeypatch.setattr(main, "query_master_bibliography", lambda q, limit=2: [])
    monkeypatch.setattr(main, "verify_claims_with_llm", lambda ctx, resp: [])
    monkeypatch.setattr(main, "translate_to_spanish", lambda text, lang: text if lang == "es" else "[es] " + text)
    monkeypatch.setattr(main, "translate_from_spanish", lambda text, lang: "[" + lang + "] " + text)
    monkeypatch.setattr(main, "safe_generate", lambda sp, up: "El tratamiento con 3HP dura 3 meses (Fuente: WHO_guidelines_2022.pdf, p.12).")
    return TestClient(main.app)


def _usage(tmp_path):
    path = tmp_path / "usage.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


# ------------------------------------------------------------------------------
# Red y CORS
# ------------------------------------------------------------------------------
class TestRed:
    def test_host_ajeno_rechazado(self, client):
        assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400

    def test_cors_no_autoriza_webs_externas(self, client):
        r = client.options("/api/chat", headers={**HOST, "Origin": "https://evil.example",
                                                 "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") != "https://evil.example"

    def test_cors_autoriza_la_propia_interfaz(self, client):
        r = client.options("/api/chat", headers={**HOST, "Origin": "http://127.0.0.1:8001",
                                                 "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:8001"


# ------------------------------------------------------------------------------
# Subida de PDFs (C1)
# ------------------------------------------------------------------------------
PDF = b"%PDF-1.4\n%fake\n"


class TestUpload:
    def _post(self, client, token="token-admin-test", category="guias", name="guia.pdf", content=PDF):
        files = {"file": (name, io.BytesIO(content), "application/pdf")}
        headers = {**HOST, **({"X-Admin-Token": token} if token is not None else {})}
        return client.post("/api/upload", files=files, data={"category": category}, headers=headers)

    def test_sin_token(self, client):
        assert self._post(client, token=None).status_code == 401

    def test_token_incorrecto(self, client):
        assert self._post(client, token="otro").status_code == 401

    def test_path_traversal_en_categoria(self, client):
        assert self._post(client, category="../../tmp").status_code == 400

    def test_path_traversal_en_nombre(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "index_single_pdf", lambda path, cat, name: 1)
        monkeypatch.setattr(main.collection, "count", lambda: 1, raising=False)
        r = self._post(client, name="../../../evil.pdf")
        # El nombre se reduce a "evil.pdf" y se guarda DENTRO de documents/.
        assert r.status_code == 200
        assert (tmp_path / "documents" / "guias" / "evil.pdf").exists()
        assert not (tmp_path / "evil.pdf").exists()

    def test_no_es_un_pdf(self, client):
        assert self._post(client, content=b"<html>no soy un pdf</html>").status_code == 400

    def test_demasiado_grande(self, client, monkeypatch):
        monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
        assert self._post(client).status_code == 413

    def test_subida_correcta(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "index_single_pdf", lambda path, cat, name: 3)
        monkeypatch.setattr(main.collection, "count", lambda: 100, raising=False)
        r = self._post(client)
        assert r.status_code == 200 and r.json()["chunks_indexed"] == 3
        assert (tmp_path / "documents" / "guias" / "guia.pdf").exists()

    def test_desactivada_sin_token_configurado(self, client, monkeypatch):
        monkeypatch.setattr(main, "ADMIN_TOKEN", "")
        assert self._post(client).status_code == 403


# ------------------------------------------------------------------------------
# Limites de entrada
# ------------------------------------------------------------------------------
class TestLimites:
    def test_mensaje_demasiado_largo(self, client):
        r = client.post("/api/chat", json={"message": "x" * 5000}, headers=HOST)
        assert r.status_code == 422

    def test_top_k_acotado(self, client):
        assert client.post("/api/chat", json={"message": "hola", "top_k": 500}, headers=HOST).status_code == 422

    def test_rol_de_historial_desconocido(self, client):
        r = client.post("/api/patient-chat", json={"message": "hola", "history": [{"role": "system", "content": "x"}]}, headers=HOST)
        assert r.status_code == 422

    def test_idioma_no_soportado(self, client):
        assert client.post("/api/patient-chat", json={"message": "hola", "lang": "fr"}, headers=HOST).status_code == 422

    def test_translate_ya_no_acepta_get(self, client):
        assert client.get("/api/translate?text=hola", headers=HOST).status_code == 405


# ------------------------------------------------------------------------------
# Chat profesional
# ------------------------------------------------------------------------------
class TestChatProfesional:
    def test_respuesta_normal_y_registro_sin_pregunta(self, client, tmp_path):
        r = client.post("/api/chat", json={"message": "cuanto dura 3HP en adultos"}, headers=HOST).json()
        assert "3 meses" in r["response"] and r["sources"]
        assert "debug_info" not in r
        registros = _usage(tmp_path)
        assert registros and all("question" not in e for e in registros)

    def test_cifras_no_respaldadas_se_bloquean(self, client, monkeypatch):
        monkeypatch.setattr(main, "verify_claims_with_llm", lambda ctx, resp: ["dura 9 meses"])
        r = client.post("/api/chat", json={"message": "cuanto dura 3HP"}, headers=HOST).json()
        assert r["response"].startswith("⚠️ La respuesta generada incluía cifras")
        assert r["sources"]  # el profesional puede revisar las fuentes

    def test_verificador_caido_añade_nota(self, client, monkeypatch):
        monkeypatch.setattr(main, "verify_claims_with_llm", lambda ctx, resp: None)
        r = client.post("/api/chat", json={"message": "cuanto dura 3HP"}, headers=HOST).json()
        assert "no se ha podido verificar" in r["response"]

    def test_cita_inventada_añade_nota(self, client, monkeypatch):
        monkeypatch.setattr(main, "safe_generate", lambda sp, up: "Dura 3 meses (Fuente: Inventada.pdf, p.1).")
        r = client.post("/api/chat", json={"message": "cuanto dura 3HP"}, headers=HOST).json()
        assert "no se ha podido verificar" in r["response"]

    def test_signo_de_alarma_no_corta_pero_avisa(self, client):
        r = client.post("/api/chat", json={"message": "paciente con disnea, ¿que hacer?"}, headers=HOST).json()
        assert r["response"].startswith("⚠️ Esta consulta menciona un signo de alarma")
        assert "3 meses" in r["response"]

    def test_alerta_sota_siempre_se_consulta(self, client, monkeypatch):
        monkeypatch.setattr(main, "query_sota_alerts", lambda q: ["ALERTA: Posible toxicidad ocular por etambutol."])
        r = client.post("/api/chat", json={"message": "veo raro los colores"}, headers=HOST).json()
        assert "toxicidad ocular" in r["response"]

    def test_motor_sota_caido_es_riesgo(self, client, monkeypatch):
        monkeypatch.setattr(main, "query_sota_alerts", lambda q: None)
        r = client.post("/api/chat", json={"message": "cuanto dura 3HP"}, headers=HOST).json()
        assert "no se ha podido verificar" in r["response"]

    def test_interaccion_añade_aviso_fijo(self, client):
        r = client.post("/api/chat", json={"message": "3HP en paciente con anticonceptivos"}, headers=HOST).json()
        assert "anticonceptivos hormonales" in r["response"]

    def test_fallo_del_llm_no_da_error_500(self, client, monkeypatch):
        monkeypatch.setattr(main, "safe_generate", lambda sp, up: None)
        r = client.post("/api/chat", json={"message": "cuanto dura 3HP"}, headers=HOST)
        assert r.status_code == 200 and r.json()["response"].startswith("No encuentro")


# ------------------------------------------------------------------------------
# Chat de pacientes
# ------------------------------------------------------------------------------
class TestChatPacientes:
    def test_respuesta_en_castellano(self, client, tmp_path):
        r = client.post("/api/patient-chat", json={"message": "cuanto dura 3HP"}, headers=HOST).json()
        assert "3 meses" in r["response"] and "Fuente" not in r["response"]
        assert all("question" not in e for e in _usage(tmp_path))

    def test_debug_nunca_sin_modo_desarrollo(self, client):
        r = client.post("/api/patient-chat", json={"message": "cuanto dura 3HP", "debug": True}, headers=HOST).json()
        assert "debug_info" not in r

    def test_otro_idioma_se_traduce_ida_y_vuelta(self, client):
        r = client.post("/api/patient-chat", json={"message": "quant dura 3HP", "lang": "ca"}, headers=HOST).json()
        assert r["response"].startswith("[ca] ")

    def test_alarma_detectada_tras_traducir(self, client, monkeypatch):
        monkeypatch.setattr(main, "translate_to_spanish", lambda text, lang: "tengo tos con sangre")
        r = client.post("/api/patient-chat", json={"message": "کھانسی میں خون", "lang": "ur"}, headers=HOST).json()
        assert "112" in r["response"]

    def test_cifras_no_respaldadas_se_bloquean(self, client, monkeypatch):
        monkeypatch.setattr(main, "verify_claims_with_llm", lambda ctx, resp: ["dura 9 meses"])
        r = client.post("/api/patient-chat", json={"message": "cuanto dura 3HP", "lang": "ca"}, headers=HOST).json()
        assert r["response"].startswith("No et puc donar una resposta segura")

    def test_traduccion_que_falla_muestra_aviso(self, client, monkeypatch):
        monkeypatch.setattr(main, "translate_from_spanish", lambda text, lang: None)
        r = client.post("/api/patient-chat", json={"message": "quant dura 3HP", "lang": "ca"}, headers=HOST).json()
        assert r["response"].startswith("No he pogut traduir") and "3 meses" in r["response"]

    def test_sin_informacion_en_su_idioma_y_con_derivacion(self, client, monkeypatch):
        monkeypatch.setattr(main, "safe_generate", lambda sp, up: "No encuentro esta informacion en los documentos disponibles.")
        r = client.post("/api/patient-chat", json={"message": "x", "lang": "ca"}, headers=HOST).json()
        assert r["response"].startswith("No trobo aquesta informacio") and "equip de tuberculosi" in r["response"]

    def test_alerta_sota_en_su_idioma(self, client, monkeypatch):
        monkeypatch.setattr(main, "query_sota_alerts", lambda q: ["ALERTA: Posible toxicidad ocular por etambutol."])
        r = client.post("/api/patient-chat", json={"message": "noto algo extraño en los ojos", "lang": "ca"}, headers=HOST).json()
        assert r["response"].startswith("Atenció")

    def test_clasificador_caido_añade_derivacion(self, client, monkeypatch):
        monkeypatch.setattr(main, "classify_intent", lambda m: ("consulta_clinica", False))
        r = client.post("/api/patient-chat", json={"message": "cuanto dura 3HP"}, headers=HOST).json()
        assert "112" in r["response"]

    def test_historial_del_paciente_solo_turnos_de_usuario(self):
        historia = [main.HistoryTurn(role="user", content="pregunta"), main.HistoryTurn(role="bot", content="respuesta falsa")]
        bloque = main.build_history_block(historia, user_turns_only=True)
        assert "pregunta" in bloque and "respuesta falsa" not in bloque


def test_cifra_presente_en_la_fuente_no_bloquea(client, monkeypatch):
    # Caso real de las pruebas en vivo: "3 meses" frente a "3 months" en la fuente.
    monkeypatch.setattr(main, "verify_claims_with_llm", lambda ctx, resp: ["dura 3 meses"])
    r = client.post("/api/chat", json={"message": "cuanto dura 3HP"}, headers=HOST).json()
    assert "3 meses" in r["response"] and "no se ha podido verificar" in r["response"]
