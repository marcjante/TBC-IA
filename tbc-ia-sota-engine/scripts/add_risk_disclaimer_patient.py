#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version para pacientes del aviso de riesgo añadido a /api/chat: cuando
hay señal de riesgo o duda (afirmaciones sin respaldo, o cobertura
baja/complementaria), se añade un aviso claro en LENGUAJE SENCILLO al
final de la respuesta real, en el idioma del paciente.

AVISO: las traducciones al arabe y urdu hechas por un asistente de IA,
pendientes de revision por un hablante nativo, igual que el resto de
mensajes en esos idiomas en este proyecto.

Aplica dos parches:
  1. backend/languages.py -> añade NOTA_RIESGO_BY_LANG + resolve_nota_riesgo()
  2. backend/main.py -> añade el aviso a result["response"] en patient_chat()

Uso:
    python3 add_risk_disclaimer_patient.py "/ruta/a/backend/languages.py" "/ruta/a/backend/main.py"
"""

import sys

# ---------------------------------------------------------------
# PARCHE 1: backend/languages.py
# ---------------------------------------------------------------

LANG_OLD = '''def resolve_canned_riesgo_autolesion(lang_code):
    return CANNED_RIESGO_AUTOLESION_BY_LANG.get(lang_code, CANNED_RIESGO_AUTOLESION_BY_LANG["es"])'''

LANG_NEW = '''def resolve_canned_riesgo_autolesion(lang_code):
    return CANNED_RIESGO_AUTOLESION_BY_LANG.get(lang_code, CANNED_RIESGO_AUTOLESION_BY_LANG["es"])


NOTA_RIESGO_BY_LANG = {
    "es": "Nota: parte de esta información no se ha podido confirmar del todo. Coméntalo con tu equipo médico antes de decidir nada.",
    "ca": "Nota: part d'aquesta informació no s'ha pogut confirmar del tot. Comenta-ho amb el teu equip mèdic abans de decidir res.",
    "ar": "ملاحظة: لم يتم تأكيد جزء من هذه المعلومات بشكل كامل. تحدث مع فريقك الطبي قبل اتخاذ أي قرار.",
    "ur": "نوٹ: اس معلومات کا کچھ حصہ مکمل طور پر تصدیق شدہ نہیں ہے۔ کوئی بھی فیصلہ کرنے سے پہلے اپنی طبی ٹیم سے بات کریں۔",
}


def resolve_nota_riesgo(lang_code):
    return NOTA_RIESGO_BY_LANG.get(lang_code, NOTA_RIESGO_BY_LANG["es"])'''

# ---------------------------------------------------------------
# PARCHE 2: backend/main.py
# ---------------------------------------------------------------

MAIN_IMPORT_OLD = "from backend.languages import resolve_lang_name, resolve_canned_no_info, resolve_canned_urgencia, resolve_canned_riesgo_autolesion"
MAIN_IMPORT_NEW = "from backend.languages import resolve_lang_name, resolve_canned_no_info, resolve_canned_urgencia, resolve_canned_riesgo_autolesion, resolve_nota_riesgo"

MAIN_OLD = '''    riesgo_o_duda = bool(llm_unsupported_claims) or internal_coverage in ("baja", "complementaria")
    if riesgo_o_duda and fragments:
        response_b = query_llamafile_response(context_text, request.message)'''

MAIN_NEW = '''    riesgo_o_duda = bool(llm_unsupported_claims) or internal_coverage in ("baja", "complementaria")

    # Aviso explicito en la respuesta real cuando hay riesgo o duda,
    # en el idioma del paciente (mismo criterio que /api/chat).
    if riesgo_o_duda:
        result["response"] = result["response"] + "\\n\\n" + resolve_nota_riesgo(request.lang)

    if riesgo_o_duda and fragments:
        response_b = query_llamafile_response(context_text, request.message)'''


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
        print("Uso: python3 add_risk_disclaimer_patient.py <ruta a backend/languages.py> <ruta a backend/main.py>")
        sys.exit(1)

    lang_path, main_path = sys.argv[1], sys.argv[2]

    print(f"Parcheando {lang_path}...")
    apply_patch(lang_path, LANG_OLD, LANG_NEW, "languages.py (resolve_nota_riesgo)")

    print(f"Parcheando {main_path}...")
    apply_patch(main_path, MAIN_IMPORT_OLD, MAIN_IMPORT_NEW, "main.py (import)")
    apply_patch(main_path, MAIN_OLD, MAIN_NEW, "main.py (aviso en patient_chat)")

    print("\nHecho. Reinicia TBC-AI para probarlo.")


if __name__ == "__main__":
    main()
