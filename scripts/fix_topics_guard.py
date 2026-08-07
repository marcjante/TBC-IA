path = "frontend_patient/script.js"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """  const topicId = detectKbTopicId(text);
  if(topicId){
    const lang = detectLang(text);
    const strings = REPLY_STRINGS[lang].topics[topicId];
    p.kbFlow = { topicId, lang, step: 0, originalText: text, answers: [] };
    return strings.opener + strings.questions[0];
  }"""

new = """  const topicId = detectKbTopicId(text);
  if(topicId){
    const lang = detectLang(text);
    const strings = (REPLY_STRINGS[lang] && REPLY_STRINGS[lang].topics[topicId]) || null;
    // En arabe/urdu no hay flujo de preguntas guiadas por tema (topics vacio a
    // proposito, ver comentario en REPLY_STRINGS): en ese caso saltamos
    // directamente a la IA en vez de abrir un flujo que no existe.
    if(!strings){
      return await buildKbAnswer(text, lang, null);
    }
    p.kbFlow = { topicId, lang, step: 0, originalText: text, answers: [] };
    return strings.opener + strings.questions[0];
  }"""

assert old in content, "No se encontro el bloque de topicId a proteger"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Guard de topics vacios aplicado")
