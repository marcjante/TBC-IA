path = "frontend_patient/script.js"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """function detectLang(text){
  return CATALAN_MARKERS.test(norm(text)) ? 'ca' : 'es';
}"""

new = """function detectLang(text){
  if (CATALAN_MARKERS.test(norm(text))) return 'ca';
  // Deteccion de escritura arabe (cubre tanto arabe estandar/darija como urdu,
  // que comparten el alfabeto arabe con extensiones). Distinguimos ur de ar
  // por la presencia de letras propias del urdu que el arabe no usa.
  const ARABIC_SCRIPT = /[\\u0600-\\u06FF\\u0750-\\u077F]/;
  const URDU_ONLY_LETTERS = /[\\u0679\\u0688\\u0691\\u06BA\\u06BE\\u06C1\\u06C2\\u06C3\\u06D2]/; // ٹ ڈ ڑ ں ھ ہ ۂ ۃ ے
  if (ARABIC_SCRIPT.test(text)) {
    return URDU_ONLY_LETTERS.test(text) ? 'ur' : 'ar';
  }
  return 'es';
}"""

assert old in content, "No se encontro detectLang"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Deteccion de arabe/urdu anadida a detectLang")
