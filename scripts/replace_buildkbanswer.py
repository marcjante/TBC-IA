path = "frontend_patient/script.js"
with open(path, encoding="utf-8") as f:
    content = f.read()

start_marker = "async function buildKbAnswer(queryText, lang, topicId){"
end_marker = "    console.warn('Cerca a la base de coneixement ha fallat', e);\n    return null;\n  }\n}"

start_idx = content.find(start_marker)
assert start_idx != -1, "No se encontro el inicio de buildKbAnswer"

end_idx = content.find(end_marker, start_idx)
assert end_idx != -1, "No se encontro el final de buildKbAnswer"
end_idx += len(end_marker)

old_function = content[start_idx:end_idx]

new_function = '''async function buildKbAnswer(queryText, lang, topicId){
  try{
    const res = await fetch('/api/patient-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: queryText, lang: lang || 'es' }),
    });
    if(!res.ok) return null;
    const data = await res.json();
    const text = (data.response || '').trim();
    if(!text) return null;
    if(text.startsWith('No encuentro esta informacion') || text.startsWith('No encuentro esta información')){
      return null;
    }
    const s = REPLY_STRINGS[lang] || REPLY_STRINGS.es;
    return s.kbIntro + text;
  }catch(e){
    console.warn('Consulta a TBC-AI ha fallat', e);
    return null;
  }
}'''

content = content.replace(old_function, new_function)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("buildKbAnswer sustituida para usar /api/patient-chat")
