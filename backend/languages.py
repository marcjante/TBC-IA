"""
TBC-AI - backend/languages.py

Utilidades de idioma para el endpoint de pacientes (/api/patient-chat):
nombres de idioma para el prompt, y el mensaje fijo de "sin informacion"
traducido a cada uno de los 4 idiomas soportados (castellano, catalan,
arabe, urdu).

FASE 7 de la auditoria: extraido de main.py, valores identicos al
original (incluidas las traducciones a arabe/urdu, que siguen pendientes
de revision por un hablante nativo -- ver README.md, seccion 10.5.3).
"""

LANG_NAMES = {
    "ca": "catalan",
    "es": "castellano",
    "ar": "arabe (fusha / arabe estandar, para que lo entienda tambien un hablante de darija marroqui)",
    "ur": "urdu",
}

CANNED_NO_INFO_BY_LANG = {
    "es": "No encuentro esta informacion en los documentos disponibles.",
    "ca": "No trobo aquesta informacio en els documents disponibles.",
    "ar": "\u0644\u0627 \u0623\u062c\u062f \u0647\u0630\u0647 \u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0629 \u0641\u064a \u0627\u0644\u0648\u062b\u0627\u0626\u0642 \u0627\u0644\u0645\u062a\u0627\u062d\u0629.",
    "ur": "\u0645\u062c\u06be\u06d2 \u062f\u0633\u062a\u06cc\u0627\u0628 \u062f\u0633\u062a\u0627\u0648\u06cc\u0632\u0627\u062a \u0645\u06cc\u06ba \u06cc\u06c1 \u0645\u0639\u0644\u0648\u0645\u0627\u062a \u0646\u06c1\u06cc\u06ba \u0645\u0644\u06cc\u06ba\u06d4",
}


def resolve_lang_name(lang_code):
    return LANG_NAMES.get(lang_code, "castellano")


def resolve_canned_no_info(lang_code):
    return CANNED_NO_INFO_BY_LANG.get(lang_code, CANNED_NO_INFO_BY_LANG["es"])
