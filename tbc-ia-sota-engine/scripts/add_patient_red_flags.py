#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Porta el Clinical Safety Router determinista (ya existente y probado en
/api/chat desde esta noche) al endpoint de pacientes (/api/patient-chat).
Hoy, si un paciente describe una emergencia conocida (etambutol+vision,
hemoptisis...), NO hay ninguna regla fija que la detecte al instante —
depende solo del sistema de alertas antiguo, que unicamente se dispara
como parte del fallback de recuperacion.

No se duplican las reglas: se reutiliza la MISMA funcion
check_deterministic_red_flags() ya definida para /api/chat, solo que
ahora tambien se llama desde patient_chat(). El mensaje de urgencia se
traduce a los 4 idiomas soportados, siguiendo el mismo patron que ya usa
CANNED_NO_INFO_BY_LANG en backend/languages.py.

AVISO: las traducciones al arabe y urdu estan hechas por un asistente de
IA sin garantia de fluidez nativa — igual que el resto de textos en esos
idiomas en este archivo (ver comentario ya existente en el modulo),
quedan pendientes de revision por un hablante nativo antes de un uso
clinico real.

Aplica dos parches:
  1. backend/languages.py -> añade CANNED_URGENCIA_BY_LANG + resolve_canned_urgencia()
  2. backend/main.py -> llama a check_deterministic_red_flags() al principio
     de patient_chat(), antes de cualquier otra cosa

Uso:
    python3 add_patient_red_flags.py "/ruta/a/backend/languages.py" "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# PARCHE 1: backend/languages.py
# ---------------------------------------------------------------

LANG_OLD = '''def resolve_lang_name(lang_code):
    return LANG_NAMES.get(lang_code, "castellano")


def resolve_canned_no_info(lang_code):
    return CANNED_NO_INFO_BY_LANG.get(lang_code, CANNED_NO_INFO_BY_LANG["es"])'''

LANG_NEW = '''CANNED_URGENCIA_BY_LANG = {
    "es": "Lo que describes puede ser una urgencia medica. Por favor, contacta ahora mismo con los servicios de emergencia (112 en España) o acude al servicio de urgencias mas cercano. Si estas en tratamiento por tuberculosis, informa tambien a tu equipo de tratamiento en cuanto puedas. Este chat no sustituye la atencion medica urgente.",
    "ca": "El que descrius pot ser una urgencia medica. Si us plau, contacta ara mateix amb els serveis d'emergencia (112 a Espanya) o vés al servei d'urgencies mes proper. Si estas en tractament per tuberculosi, informa tambe al teu equip de tractament tan aviat com puguis. Aquest xat no substitueix l'atencio medica urgent.",
    "ar": "ما تصفه قد يكون حالة طبية طارئة. يرجى الاتصال الآن بخدمات الطوارئ (112 في إسبانيا) أو التوجه إلى أقرب قسم للطوارئ. إذا كنت تحت علاج السل، أخبر أيضا فريق العلاج الخاص بك في أقرب وقت ممكن. هذه المحادثة لا تغني عن الرعاية الطبية العاجلة.",
    "ur": "جو آپ بیان کر رہے ہیں وہ طبی ہنگامی صورتحال ہو سکتی ہے۔ براہ مہربانی ابھی ہنگامی خدمات (سپین میں 112) سے رابطہ کریں یا قریب ترین ایمرجنسی سے رجوع کریں۔ اگر آپ تپ دق کے علاج میں ہیں تو جلد از جلد اپنی علاج ٹیم کو بھی بتائیں۔ یہ چیٹ فوری طبی امداد کا متبادل نہیں ہے۔",
}


def resolve_lang_name(lang_code):
    return LANG_NAMES.get(lang_code, "castellano")


def resolve_canned_no_info(lang_code):
    return CANNED_NO_INFO_BY_LANG.get(lang_code, CANNED_NO_INFO_BY_LANG["es"])


def resolve_canned_urgencia(lang_code):
    return CANNED_URGENCIA_BY_LANG.get(lang_code, CANNED_URGENCIA_BY_LANG["es"])'''

# ---------------------------------------------------------------
# PARCHE 2: backend/main.py
# ---------------------------------------------------------------

MAIN_IMPORT_OLD = "from backend.languages import resolve_lang_name, resolve_canned_no_info"
MAIN_IMPORT_NEW = "from backend.languages import resolve_lang_name, resolve_canned_no_info, resolve_canned_urgencia"

MAIN_OLD = '''@app.post("/api/patient-chat")
def patient_chat(request: PatientChatRequest):
    lang_name = resolve_lang_name(request.lang)
    canned_no_info = resolve_canned_no_info(request.lang)

    retrieval_query = build_retrieval_query(request.message, request.history)'''

MAIN_NEW = '''@app.post("/api/patient-chat")
def patient_chat(request: PatientChatRequest):
    lang_name = resolve_lang_name(request.lang)
    canned_no_info = resolve_canned_no_info(request.lang)

    # Router de seguridad determinista (mismo que /api/chat, sin
    # duplicar las reglas): reconoce patrones de riesgo YA CONOCIDOS
    # por palabras clave, de forma instantanea, sin depender de que
    # ningun modelo responda. Se ejecuta antes que cualquier otra cosa.
    red_flag = check_deterministic_red_flags(request.message)
    if red_flag:
        log_usage_pattern("/api/patient-chat", f"red_flag_{red_flag}", lang=request.lang)
        return {"response": resolve_canned_urgencia(request.lang)}

    retrieval_query = build_retrieval_query(request.message, request.history)'''


def apply_patch(path, old, new, label):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if new in content:
        print(f"  {label}: ya estaba aplicado (no se ha tocado nada).")
        return

    count = content.count(old)
    if count == 0:
        print(f"  {label}: ABORTADO, no se encontró el bloque esperado. No se ha escrito nada de este paso.")
        sys.exit(1)
    if count > 1:
        print(f"  {label}: ABORTADO, el bloque aparece {count} veces (debería ser único). No se ha escrito nada de este paso.")
        sys.exit(1)

    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  {label}: aplicado correctamente.")


def main():
    if len(sys.argv) != 3:
        print("Uso: python3 add_patient_red_flags.py <ruta a backend/languages.py> <ruta a backend/main.py>")
        sys.exit(1)

    lang_path, main_path = sys.argv[1], sys.argv[2]

    print(f"Parcheando {lang_path}...")
    apply_patch(lang_path, LANG_OLD, LANG_NEW, "languages.py (resolve_canned_urgencia)")

    print(f"Parcheando {main_path}...")
    apply_patch(main_path, MAIN_IMPORT_OLD, MAIN_IMPORT_NEW, "main.py (import)")
    apply_patch(main_path, MAIN_OLD, MAIN_NEW, "main.py (llamada al router de seguridad)")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
