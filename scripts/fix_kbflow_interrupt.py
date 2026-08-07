path = "frontend_patient/script.js"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """  if(p.kbFlow){
    const lang = p.kbFlow.lang || detectLang(text);
    const currentStrings = (REPLY_STRINGS[lang] || REPLY_STRINGS.es).topics[p.kbFlow.topicId];
    const maybeNewTopicId = detectKbTopicId(text);
    if(!currentStrings){ delete p.kbFlow; return null; }"""

new = """  if(p.kbFlow){
    const lang = p.kbFlow.lang || detectLang(text);
    const currentStrings = (REPLY_STRINGS[lang] || REPLY_STRINGS.es).topics[p.kbFlow.topicId];
    const maybeNewTopicId = detectKbTopicId(text);
    if(!currentStrings){ delete p.kbFlow; return null; }

    // Si el pacient escriu una pregunta clarament independent (acaba en '?')
    // mentre hi ha un flux de seguiment obert, no l'interpretem com a resposta
    // a la pregunta anterior: cancel·lem el flux i responem la pregunta nova.
    if(/[?？]\\s*$/.test(text.trim())){
      delete p.kbFlow;
      return await buildKbAnswer(text, detectLang(text), null);
    }"""

assert old in content, "No se encontro el bloque exacto de p.kbFlow"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Interrupcion de flujo por pregunta nueva aplicada")
