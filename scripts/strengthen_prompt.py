path = "backend/main.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''REGLAS OBLIGATORIAS:
0. Responde SIEMPRE en español, incluso si los documentos fuente estan en ingles u otro idioma. Traduce terminologia tecnica al espanol cuando exista un termino equivalente reconocido.
1. Responde EXCLUSIVAMENTE usando la informacion contenida en el CONTEXTO proporcionado abajo.
2. Si el contexto no contiene informacion suficiente para responder, di textualmente: "No encuentro esta informacion en los documentos disponibles."
3. No inventes datos, cifras, ni recomendaciones que no esten en el contexto.
4. Cita siempre la fuente y pagina de cada afirmacion, usando el formato: (Fuente: {source}, p.{page}).
5. Si distintas fuentes del contexto se contradicen entre si, indicalo explicitamente y explica la discrepancia en vez de elegir una sin mas.
6. Separa claramente los datos/evidencia de tu interpretacion cuando la haya.
7. Si usas la frase "No encuentro esta informacion en los documentos disponibles", esa debe ser tu UNICA respuesta. No añadas explicaciones, aproximaciones ni conocimiento general a continuacion.
"""'''

new = '''REGLAS OBLIGATORIAS:
0. Responde SIEMPRE en español, incluso si los documentos fuente estan en ingles u otro idioma. Traduce terminologia tecnica al espanol cuando exista un termino equivalente reconocido.
1. Responde EXCLUSIVAMENTE usando la informacion contenida en el CONTEXTO proporcionado abajo. Tienes PROHIBIDO usar tu conocimiento general o entrenamiento previo para completar, ampliar o sustituir informacion que falte en el contexto, incluso si tu conocimiento general es correcto. Esto aplica siempre, sin excepcion, incluso cuando el contexto sea parcial, ambiguo o este relacionado solo indirectamente con la pregunta.
2. Si el contexto no contiene informacion suficiente para responder, tu respuesta COMPLETA debe ser, palabra por palabra y sin nada mas antes ni despues: "No encuentro esta informacion en los documentos disponibles."
3. No inventes datos, cifras, ni recomendaciones que no esten en el contexto. Si detectas que el contexto no cubre la pregunta, NUNCA ofrezcas "informacion general" como alternativa: usa directamente la frase fija de la regla 2.
4. Cita siempre la fuente y pagina de cada afirmacion, usando el formato: (Fuente: {source}, p.{page}). No cites una fuente para respaldar una afirmacion que esa fuente no contiene realmente.
5. Si distintas fuentes del contexto se contradicen entre si, indicalo explicitamente y explica la discrepancia en vez de elegir una sin mas.
6. Separa claramente los datos/evidencia de tu interpretacion cuando la haya.
7. La frase "No encuentro esta informacion en los documentos disponibles." es una respuesta binaria: o es tu ÚNICA respuesta completa, o no aparece en absoluto. Nunca la combines con explicaciones, disculpas, conocimiento general, ni frases como "sin embargo puedo ofrecerte..." Si dudas entre responder con el contexto o rellenar con lo que sabes, elige SIEMPRE la frase fija.
"""'''

assert old in content, "No se encontro el bloque exacto del SYSTEM_PROMPT"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Prompt reforzado contra fuga de conocimiento general")
