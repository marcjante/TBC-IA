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


# ------------------------------------------------------------------------------
# Revision de seguridad clinica, octubre 2026. Las versiones en arabe y urdu
# estan PENDIENTES DE REVISION POR UN HABLANTE NATIVO, igual que las anteriores.
# ------------------------------------------------------------------------------

# M2: el mensaje de "sin informacion" indica ademas a quien acudir. Se
# mantiene el comienzo de la frase original para que detect_no_info_statement
# y el frontend sigan reconociendolo.
REFERRAL_BY_LANG = {
    "es": "Consulta esta duda con tu equipo de tuberculosis o con tu centro de salud.",
    "ca": "Consulta aquest dubte amb el teu equip de tuberculosi o amb el teu centre de salut.",
    "ar": "استشر فريق علاج السل أو مركزك الصحي بخصوص هذا السؤال.",
    "ur": "اس سوال کے بارے میں اپنی تپ دق کی علاج ٹیم یا اپنے صحت مرکز سے مشورہ کریں۔",
}

# A1: la respuesta generada contenia cifras (dosis, duraciones) que no se
# han podido verificar contra las fuentes, asi que no se muestra.
CANNED_BLOQUEO_CIFRAS_BY_LANG = {
    "es": "No puedo darte una respuesta segura a esta pregunta: incluye dosis o duraciones que no he podido comprobar en las guías clínicas. Pregúntalo a tu equipo de tuberculosis o a tu farmacéutico.",
    "ca": "No et puc donar una resposta segura a aquesta pregunta: inclou dosis o durades que no he pogut comprovar a les guies clíniques. Pregunta-ho al teu equip de tuberculosi o al teu farmacèutic.",
    "ar": "لا أستطيع أن أعطيك إجابة آمنة على هذا السؤال: فهو يتضمن جرعات أو مدد علاج لم أتمكن من التحقق منها في الإرشادات السريرية. اسأل فريق علاج السل أو الصيدلي.",
    "ur": "میں اس سوال کا محفوظ جواب نہیں دے سکتا: اس میں دوا کی مقدار یا علاج کی مدت شامل ہے جس کی میں طبی رہنما اصولوں میں تصدیق نہیں کر سکا۔ اپنی تپ دق کی علاج ٹیم یا فارماسسٹ سے پوچھیں۔",
}

# A3: el motor complementario detecta una posible toxicidad (p. ej. ocular
# por etambutol).
CANNED_ALERTA_TOXICIDAD_BY_LANG = {
    "es": "Atención: lo que describes podría ser un efecto adverso importante de la medicación. Contacta hoy mismo con tu equipo de tuberculosis y, si empeora, acude a urgencias (112). No dejes ni cambies la medicación por tu cuenta.",
    "ca": "Atenció: el que descrius podria ser un efecte advers important de la medicació. Contacta avui mateix amb el teu equip de tuberculosi i, si empitjora, ves a urgències (112). No deixis ni canviïs la medicació pel teu compte.",
    "ar": "انتبه: ما تصفه قد يكون أثرا جانبيا مهما للدواء. اتصل اليوم بفريق علاج السل، وإذا ساءت حالتك توجه إلى الطوارئ (112). لا توقف الدواء ولا تغيره من تلقاء نفسك.",
    "ur": "توجہ دیں: جو آپ بیان کر رہے ہیں وہ دوا کا ایک اہم مضر اثر ہو سکتا ہے۔ آج ہی اپنی تپ دق کی علاج ٹیم سے رابطہ کریں اور اگر حالت بگڑے تو ایمرجنسی (112) جائیں۔ اپنی مرضی سے دوا بند یا تبدیل نہ کریں۔",
}

# A6: la traduccion no ha superado la comprobacion de cifras; se muestra la
# respuesta en castellano precedida de este aviso.
TRADUCCION_NO_VERIFICADA_BY_LANG = {
    "ca": "No he pogut traduir aquesta resposta amb seguretat. Te la mostro en castellà; si tens dubtes, pregunta-ho al teu equip de tuberculosi.",
    "ar": "لم أتمكن من ترجمة هذه الإجابة بشكل آمن. أعرضها لك بالإسبانية؛ إذا كان لديك أي شك، اسأل فريق علاج السل.",
    "ur": "میں اس جواب کا محفوظ ترجمہ نہیں کر سکا۔ یہ ہسپانوی زبان میں دکھا رہا ہوں؛ اگر کوئی شک ہو تو اپنی تپ دق کی علاج ٹیم سے پوچھیں۔",
}


def _by_lang(table, lang_code):
    return table.get(lang_code, table["es"])


def resolve_no_info_with_referral(lang_code):
    return resolve_canned_no_info(lang_code) + " " + _by_lang(REFERRAL_BY_LANG, lang_code)


def resolve_bloqueo_cifras(lang_code):
    return _by_lang(CANNED_BLOQUEO_CIFRAS_BY_LANG, lang_code)


def resolve_alerta_toxicidad(lang_code):
    return _by_lang(CANNED_ALERTA_TOXICIDAD_BY_LANG, lang_code)


def resolve_traduccion_no_verificada(lang_code):
    return TRADUCCION_NO_VERIFICADA_BY_LANG.get(lang_code, "")
