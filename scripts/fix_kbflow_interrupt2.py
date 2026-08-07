path = "frontend_patient/script.js"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """    // Si el pacient escriu una pregunta clarament independent (acaba en '?')
    // mentre hi ha un flux de seguiment obert, no l'interpretem com a resposta
    // a la pregunta anterior: cancel·lem el flux i responem la pregunta nova.
    if(/[?？]\\s*$/.test(text.trim())){
      delete p.kbFlow;
      return await buildKbAnswer(text, detectLang(text), null);
    }"""

new = """    // Si el pacient escriu una pregunta clarament independent (acaba en '?'
    // o comenca amb una paraula interrogativa habitual) mentre hi ha un flux
    // de seguiment obert, no l'interpretem com a resposta a la pregunta
    // anterior: cancel·lem el flux i responem la pregunta nova.
    const looksLikeNewQuestion = /[?？]\\s*$/.test(text.trim()) ||
      /^\\s*(que|qué|com|cómo|quan|cuándo|cuando|on|dónde|donde|per que|per qu|porque|por que|por qué|puc|puedo|es cert|es cierto|hi ha|hay|existe|existeix|quin|cuál|cual|quins|cuáles|cuales)\\b/i.test(text.trim());
    if(looksLikeNewQuestion){
      delete p.kbFlow;
      return await buildKbAnswer(text, detectLang(text), null);
    }"""

assert old in content, "No se encontro el bloque anterior del fix 1"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Deteccion ampliada de preguntas nuevas aplicada")
