path = "frontend_patient/script.js"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """/* Precarrega la base de coneixement TB (kb/buscador.js) en segon pla,
   perquè estigui llesta quan el pacient escrigui el primer missatge. */
if(window.TB_KB){
  window.TB_KB.loadIndex().catch(e=> console.warn('Base de coneixement TB no disponible:', e));
}"""

new = """/* La base de coneixement TB (kb/buscador.js) ja no es precarrega:
   buildKbAnswer() usa /api/patient-chat en comptes de window.TB_KB.
   Els fitxers de kb/ es conserven per si es vol tornar a usar el
   buscador estatic com a alternativa, pero no es carreguen per defecte. */"""

assert old in content, "No se encontro el bloque exacto de precarga"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Precarga de TB_KB eliminada, comentario explicativo dejado en su lugar")
