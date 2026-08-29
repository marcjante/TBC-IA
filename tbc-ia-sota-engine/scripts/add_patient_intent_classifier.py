#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Porta el clasificador de intencion por LLM (classify_intent, ya
existente y probado en /api/chat) al endpoint de pacientes. Ademas de
las urgencias medicas fisicas (ya cubiertas por el router determinista
de la pieza 1), esto añade deteccion de riesgo de autolesion mediante
el modelo, con un mensaje de recursos de crisis reales (linea 024,
verificada activa en 2026) traducido a los 4 idiomas soportados.

AVISO: las traducciones al arabe y urdu de este mensaje de crisis estan
hechas por un asistente de IA sin garantia de fluidez nativa, igual que
el resto de textos en esos idiomas en este modulo — pendientes de
revision por un hablante nativo antes de un uso clinico real. El numero
024 y el 112 se mantienen sin traducir en todos los idiomas al ser
numeros de telefono reales de España.

Aplica dos parches:
  1. backend/languages.py -> añade CANNED_RIESGO_AUTOLESION_BY_LANG +
     resolve_canned_riesgo_autolesion()
  2. backend/main.py -> llama a classify_intent() en patient_chat(),
     justo despues del router determinista de la pieza 1

Uso:
    python3 add_patient_intent_classifier.py "/ruta/a/backend/languages.py" "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# PARCHE 1: backend/languages.py
# ---------------------------------------------------------------

LANG_OLD = '''def resolve_canned_urgencia(lang_code):
    return CANNED_URGENCIA_BY_LANG.get(lang_code, CANNED_URGENCIA_BY_LANG["es"])'''

LANG_NEW = '''def resolve_canned_urgencia(lang_code):
    return CANNED_URGENCIA_BY_LANG.get(lang_code, CANNED_URGENCIA_BY_LANG["es"])


CANNED_RIESGO_AUTOLESION_BY_LANG = {
    "es": "Lamento que estes pasando por un momento tan dificil. Por favor, no te quedes solo con esto: puedes llamar al 024 (linea de atencion a la conducta suicida, gratuita, disponible las 24 horas en España) o al 112 si hay riesgo inmediato. Tambien puedes contactar con tu equipo de tratamiento o con alguien de confianza ahora mismo. Este chat no sustituye la ayuda profesional que necesitas.",
    "ca": "Sento molt que estiguis passant per un moment tan dificil. Si us plau, no et quedis sol amb aixo: pots trucar al 024 (linia d'atencio a la conducta suicida, gratuita, disponible les 24 hores a Espanya) o al 112 si hi ha risc immediat. Tambe pots contactar amb el teu equip de tractament o amb algu de confiança ara mateix. Aquest xat no substitueix l'ajuda professional que necessites.",
    "ar": "يؤسفني أنك تمر بلحظة صعبة كهذه. من فضلك لا تبق وحيدا مع هذا: يمكنك الاتصال بالرقم 024 (خط الدعم النفسي للسلوك الانتحاري، مجاني، متاح على مدار 24 ساعة في إسبانيا) أو 112 إذا كان هناك خطر فوري. يمكنك أيضا التواصل مع فريق العلاج الخاص بك أو مع شخص تثق به الآن. هذه المحادثة لا تغني عن المساعدة المهنية التي تحتاجها.",
    "ur": "مجھے افسوس ہے کہ آپ اس مشکل وقت سے گزر رہے ہیں۔ براہ مہربانی اکیلے مت رہیں: آپ 024 پر کال کر سکتے ہیں (خودکشی کے رجحان کی مدد کی لائن، مفت، سپین میں 24 گھنٹے دستیاب) یا فوری خطرہ ہونے کی صورت میں 112 پر۔ آپ اپنی علاج ٹیم یا کسی قابل اعتماد شخص سے بھی ابھی رابطہ کر سکتے ہیں۔ یہ چیٹ اس پیشہ ورانہ مدد کا متبادل نہیں ہے جس کی آپ کو ضرورت ہے۔",
}


def resolve_canned_riesgo_autolesion(lang_code):
    return CANNED_RIESGO_AUTOLESION_BY_LANG.get(lang_code, CANNED_RIESGO_AUTOLESION_BY_LANG["es"])'''

# ---------------------------------------------------------------
# PARCHE 2: backend/main.py
# ---------------------------------------------------------------

MAIN_IMPORT_OLD = "from backend.languages import resolve_lang_name, resolve_canned_no_info, resolve_canned_urgencia"
MAIN_IMPORT_NEW = "from backend.languages import resolve_lang_name, resolve_canned_no_info, resolve_canned_urgencia, resolve_canned_riesgo_autolesion"

MAIN_OLD = '''    red_flag = check_deterministic_red_flags(request.message)
    if red_flag:
        log_usage_pattern("/api/patient-chat", f"red_flag_{red_flag}", lang=request.lang)
        return {"response": resolve_canned_urgencia(request.lang)}

    retrieval_query = build_retrieval_query(request.message, request.history)'''

MAIN_NEW = '''    red_flag = check_deterministic_red_flags(request.message)
    if red_flag:
        log_usage_pattern("/api/patient-chat", f"red_flag_{red_flag}", lang=request.lang)
        return {"response": resolve_canned_urgencia(request.lang)}

    # Clasificador de intencion por LLM (mismo que /api/chat): cubre
    # casos que las reglas fijas de la pieza 1 no reconocen por palabras
    # clave concretas, y ademas detecta riesgo de autolesion, con
    # recursos de crisis reales en el idioma del paciente.
    intencion = classify_intent(request.message)
    if intencion == "urgencia_medica":
        log_usage_pattern("/api/patient-chat", "urgencia_medica_general", lang=request.lang)
        return {"response": resolve_canned_urgencia(request.lang)}
    if intencion == "riesgo_autolesion":
        log_usage_pattern("/api/patient-chat", "riesgo_autolesion", lang=request.lang)
        return {"response": resolve_canned_riesgo_autolesion(request.lang)}

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
        print("Uso: python3 add_patient_intent_classifier.py <ruta a backend/languages.py> <ruta a backend/main.py>")
        sys.exit(1)

    lang_path, main_path = sys.argv[1], sys.argv[2]

    print(f"Parcheando {lang_path}...")
    apply_patch(lang_path, LANG_OLD, LANG_NEW, "languages.py (resolve_canned_riesgo_autolesion)")

    print(f"Parcheando {main_path}...")
    apply_patch(main_path, MAIN_IMPORT_OLD, MAIN_IMPORT_NEW, "main.py (import)")
    apply_patch(main_path, MAIN_OLD, MAIN_NEW, "main.py (llamada a classify_intent)")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
