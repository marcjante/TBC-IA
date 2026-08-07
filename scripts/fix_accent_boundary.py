path = "frontend_patient/script.js"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """    const looksLikeNewQuestion = /[?？]\\s*$/.test(text.trim()) ||
      /^\\s*(que|qué|com|cómo|quan|cuándo|cuando|on|dónde|donde|per que|per qu|porque|por que|por qué|puc|puedo|es cert|es cierto|hi ha|hay|existe|existeix|quin|cuál|cual|quins|cuáles|cuales)\\b/i.test(text.trim());"""

new = """    const looksLikeNewQuestion = /[?？]\\s*$/.test(text.trim()) ||
      /^\\s*(que|qué|com|cómo|quan|cuándo|cuando|on|dónde|donde|per que|per qu|porque|por que|por qué|puc|puedo|es cert|es cierto|hi ha|hay|existe|existeix|quin|cuál|cual|quins|cuáles|cuales)(\\s|$)/i.test(text.trim());"""

assert old in content, "No se encontro el patron con \\\\b a corregir"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Bug de limite de palabra con acentos corregido")
