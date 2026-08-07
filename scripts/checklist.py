"""
TBC-AI - Checklist de verificacion completa del sistema
"""
import requests

API = "http://127.0.0.1:8000"
checks = []

def check(name, condition, detail=""):
    status = "OK" if condition else "FALLO"
    checks.append((name, status, detail))
    print(f"[{status}] {name}" + (f" - {detail}" if detail and status == "FALLO" else ""))

# 1. Salud del backend
r = requests.get(f"{API}/api/health").json()
check("Backend activo", r.get("status") == "ok")
check("Modelo correcto (llama3.1:8b)", r.get("model") == "llama3.1:8b", f"modelo actual: {r.get('model')}")
check("Documentos indexados (~4972)", r.get("documentos_indexados", 0) > 4900, f"actual: {r.get('documentos_indexados')}")

# 2. Chat de guias: pregunta legitima con cobertura
r = requests.post(f"{API}/api/chat", json={"message": "Que es el IGRA?"}).json()
check("Guias: pregunta legitima responde con fuentes", len(r.get("sources", [])) > 0, r.get("response", "")[:80])

# 3. Chat de guias: pregunta irrelevante bloqueada
r = requests.post(f"{API}/api/chat", json={"message": "cual es la capital de Francia"}).json()
check("Guias: pregunta irrelevante bloqueada sin fuentes", r.get("sources") == [] and "No encuentro" in r.get("response", ""))

# 4. Chat de pacientes: pregunta general responde en lenguaje sencillo
r = requests.post(f"{API}/api/patient-chat", json={"message": "Que es la tuberculosis latente", "lang": "es"}).json()
resp = r.get("response", "")
check("Pacientes: responde sin mencionar PDF/paginas", ".pdf" not in resp.lower() and "fuente:" not in resp.lower(), resp[:80])

# 5. Chat de pacientes: pregunta irrelevante bloqueada con frase fija exacta
r = requests.post(f"{API}/api/patient-chat", json={"message": "hola como estas", "lang": "es"}).json()
check("Pacientes: frase fija exacta en negativas", r.get("response", "").startswith("No encuentro"), r.get("response", ""))

# 6. Idioma arabe
r = requests.post(f"{API}/api/patient-chat", json={"message": "ما هو مرض السل؟", "lang": "ar"}).json()
resp_ar = r.get("response", "")
check("Arabe: responde en escritura arabe", any("\u0600" <= c <= "\u06FF" for c in resp_ar), resp_ar[:60])

# 7. Idioma urdu
r = requests.post(f"{API}/api/patient-chat", json={"message": "تپ دق کیا ہے؟", "lang": "ur"}).json()
resp_ur = r.get("response", "")
check("Urdu: responde en escritura urdu/arabe", any("\u0600" <= c <= "\u06FF" for c in resp_ur), resp_ur[:60])

# 8. Guardrail: BCG no debe alucinar nombre falso
r = requests.post(f"{API}/api/chat", json={"message": "En que situaciones esta indicada la vacuna BCG"}).json()
resp_bcg = r.get("response", "")
check("BCG: no menciona nombres inventados", "coleil" not in resp_bcg.lower() and "gridel" not in resp_bcg.lower())

print("\n--- RESUMEN ---")
ok = sum(1 for _, s, _ in checks if s == "OK")
print(f"{ok}/{len(checks)} verificaciones correctas")
for name, status, detail in checks:
    if status == "FALLO":
        print(f"REVISAR: {name} -- {detail}")
