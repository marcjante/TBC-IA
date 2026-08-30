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


CANNED_URGENCIA_BY_LANG = {
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
    return CANNED_URGENCIA_BY_LANG.get(lang_code, CANNED_URGENCIA_BY_LANG["es"])


CANNED_RIESGO_AUTOLESION_BY_LANG = {
    "es": "Lamento que estes pasando por un momento tan dificil. Por favor, no te quedes solo con esto: puedes llamar al 024 (linea de atencion a la conducta suicida, gratuita, disponible las 24 horas en España) o al 112 si hay riesgo inmediato. Tambien puedes contactar con tu equipo de tratamiento o con alguien de confianza ahora mismo. Este chat no sustituye la ayuda profesional que necesitas.",
    "ca": "Sento molt que estiguis passant per un moment tan dificil. Si us plau, no et quedis sol amb aixo: pots trucar al 024 (linia d'atencio a la conducta suicida, gratuita, disponible les 24 hores a Espanya) o al 112 si hi ha risc immediat. Tambe pots contactar amb el teu equip de tractament o amb algu de confiança ara mateix. Aquest xat no substitueix l'ajuda professional que necessites.",
    "ar": "يؤسفني أنك تمر بلحظة صعبة كهذه. من فضلك لا تبق وحيدا مع هذا: يمكنك الاتصال بالرقم 024 (خط الدعم النفسي للسلوك الانتحاري، مجاني، متاح على مدار 24 ساعة في إسبانيا) أو 112 إذا كان هناك خطر فوري. يمكنك أيضا التواصل مع فريق العلاج الخاص بك أو مع شخص تثق به الآن. هذه المحادثة لا تغني عن المساعدة المهنية التي تحتاجها.",
    "ur": "مجھے افسوس ہے کہ آپ اس مشکل وقت سے گزر رہے ہیں۔ براہ مہربانی اکیلے مت رہیں: آپ 024 پر کال کر سکتے ہیں (خودکشی کے رجحان کی مدد کی لائن، مفت، سپین میں 24 گھنٹے دستیاب) یا فوری خطرہ ہونے کی صورت میں 112 پر۔ آپ اپنی علاج ٹیم یا کسی قابل اعتماد شخص سے بھی ابھی رابطہ کر سکتے ہیں۔ یہ چیٹ اس پیشہ ورانہ مدد کا متبادل نہیں ہے جس کی آپ کو ضرورت ہے۔",
}


def resolve_canned_riesgo_autolesion(lang_code):
    return CANNED_RIESGO_AUTOLESION_BY_LANG.get(lang_code, CANNED_RIESGO_AUTOLESION_BY_LANG["es"])


NOTA_RIESGO_BY_LANG = {
    "es": "Nota: parte de esta información no se ha podido confirmar del todo. Coméntalo con tu equipo médico antes de decidir nada.",
    "ca": "Nota: part d'aquesta informació no s'ha pogut confirmar del tot. Comenta-ho amb el teu equip mèdic abans de decidir res.",
    "ar": "ملاحظة: لم يتم تأكيد جزء من هذه المعلومات بشكل كامل. تحدث مع فريقك الطبي قبل اتخاذ أي قرار.",
    "ur": "نوٹ: اس معلومات کا کچھ حصہ مکمل طور پر تصدیق شدہ نہیں ہے۔ کوئی بھی فیصلہ کرنے سے پہلے اپنی طبی ٹیم سے بات کریں۔",
}


def resolve_nota_riesgo(lang_code):
    return NOTA_RIESGO_BY_LANG.get(lang_code, NOTA_RIESGO_BY_LANG["es"])
