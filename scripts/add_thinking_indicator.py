path = "frontend_patient/script.js"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = """async function sendMessage(){
  const input = document.getElementById('msgInput');
  const text = input.value.trim();
  if(!text) return;
  const p = patients[currentPatientId];
  p.messages.push({from:'patient', text, time:new Date().toISOString()});
  const tr = triage(text);
  const lang = detectLang(text);

  if(tr.level==='urgent' || tr.level==='moderate'){
    // Seguretat sempre primer i sense excepcions: la resposta de triatge es
    // mostra sempre, íntegra, i mai es barreja amb la conversa de la base
    // de coneixement (advanceKbConversation ja cancel·la qualsevol flux obert).
    const reply = botReply(tr, lang);
    p.messages.push({from:'bot', text:reply, time:new Date().toISOString(), level: tr.level});
    if(!p.alerts) p.alerts = [];
    p.alerts.push({level:tr.level, label:tr.label, text, acknowledged:false, time:new Date().toISOString()});
    await savePatient(p);
    input.value='';
    renderChatView();
    return;
  }

  if(tr.level==='mild'){
    // Consell específic (oblit de dosi, símptoma lleu): sempre útil, es manté.
    const reply = botReply(tr, lang);
    p.messages.push({from:'bot', text:reply, time:new Date().toISOString(), level: tr.level});
  }

  // Conversa amb la base de coneixement: pregunta de seguiment o resposta final.
  const kbText = await advanceKbConversation(p, text, tr);
  if(kbText){
    p.messages.push({from:'bot', text:kbText, time:new Date().toISOString(), level:'info'});
  } else if(tr.level==='info'){
    // Només mostrem l'avís genèric quan no hi ha cap resposta conversacional
    // més concreta a oferir, per no repetir sempre el mateix text llarg.
    const reply = botReply(tr, lang);
    p.messages.push({from:'bot', text:reply, time:new Date().toISOString(), level: tr.level});
  }
  await savePatient(p);
  input.value='';
  renderChatView();
}"""

new = """async function sendMessage(){
  const input = document.getElementById('msgInput');
  const sendBtn = document.getElementById('sendBtn');
  const text = input.value.trim();
  if(!text) return;
  // Bloqueig immediat: evita que un doble clic o un Enter repetit mentre
  // s'espera resposta enviin el mateix missatge diverses vegades.
  if(sendBtn && sendBtn.disabled) return;

  const p = patients[currentPatientId];
  p.messages.push({from:'patient', text, time:new Date().toISOString()});
  const tr = triage(text);
  const lang = detectLang(text);

  if(tr.level==='urgent' || tr.level==='moderate'){
    // Seguretat sempre primer i sense excepcions: la resposta de triatge es
    // mostra sempre, íntegra, i mai es barreja amb la conversa de la base
    // de coneixement (advanceKbConversation ja cancel·la qualsevol flux obert).
    const reply = botReply(tr, lang);
    p.messages.push({from:'bot', text:reply, time:new Date().toISOString(), level: tr.level});
    if(!p.alerts) p.alerts = [];
    p.alerts.push({level:tr.level, label:tr.label, text, acknowledged:false, time:new Date().toISOString()});
    await savePatient(p);
    input.value='';
    renderChatView();
    return;
  }

  if(tr.level==='mild'){
    // Consell específic (oblit de dosi, símptoma lleu): sempre útil, es manté.
    const reply = botReply(tr, lang);
    p.messages.push({from:'bot', text:reply, time:new Date().toISOString(), level: tr.level});
  }

  input.value='';
  renderChatView();
  showThinkingIndicator();
  if(sendBtn) sendBtn.disabled = true;
  if(input) input.disabled = true;

  try{
    // Conversa amb la base de coneixement: pregunta de seguiment o resposta final.
    const kbText = await advanceKbConversation(p, text, tr);
    if(kbText){
      p.messages.push({from:'bot', text:kbText, time:new Date().toISOString(), level:'info'});
    } else if(tr.level==='info'){
      // Només mostrem l'avís genèric quan no hi ha cap resposta conversacional
      // més concreta a oferir, per no repetir sempre el mateix text llarg.
      const reply = botReply(tr, lang);
      p.messages.push({from:'bot', text:reply, time:new Date().toISOString(), level: tr.level});
    }
    await savePatient(p);
  } finally {
    hideThinkingIndicator();
    const sendBtn2 = document.getElementById('sendBtn');
    const input2 = document.getElementById('msgInput');
    if(sendBtn2) sendBtn2.disabled = false;
    if(input2) input2.disabled = false;
    renderChatView();
  }
}

function showThinkingIndicator(){
  const chatArea = document.getElementById('chatArea');
  if(!chatArea) return;
  const el = document.createElement('div');
  el.id = 'thinkingIndicator';
  el.style.cssText = 'padding:10px 14px;color:#5B6560;font-style:italic;font-size:14px;';
  el.textContent = 'Pensant la resposta...';
  chatArea.appendChild(el);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function hideThinkingIndicator(){
  const el = document.getElementById('thinkingIndicator');
  if(el) el.remove();
}"""

assert old in content, "No se encontro sendMessage completa"
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Indicador de 'pensando' y bloqueo de doble envio anadidos")
