(function(){
  const body = document.body;
  const role = body.dataset.role || 'patient';
  const patientId = body.dataset.patientId || '00001';
  const listEl = document.getElementById('directMessages');
  const input = document.getElementById('directInput');
  const sendBtn = document.getElementById('directSend');

  const render = (messages) => {
    listEl.innerHTML = '';
    messages.forEach((m) => {
      const wrap = document.createElement('div');
      wrap.className = 'msg ' + (m.sender === 'doctor' ? 'doctor' : 'patient');
      const meta = document.createElement('div');
      meta.className = 'msg-meta';
      meta.textContent = (m.senderName || m.sender) + ' ? ' + (m.timestamp || '');
      const text = document.createElement('div');
      text.textContent = m.text || '';
      wrap.appendChild(meta);
      wrap.appendChild(text);
      listEl.appendChild(wrap);
    });
    listEl.scrollTop = listEl.scrollHeight;
  };

  const load = async () => {
    try {
      const res = await fetch(`/api/direct_chat/messages?patient_id=${patientId}`);
      const data = await res.json();
      if (data && data.messages) {
        render(data.messages);
      }
    } catch {}
  };

  const send = async () => {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    try {
      await fetch('/api/direct_chat/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, patient_id: patientId })
      });
      await load();
    } catch {}
  };

  sendBtn.addEventListener('click', send);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') send();
  });

  load();
  setInterval(load, 3000);
})();
