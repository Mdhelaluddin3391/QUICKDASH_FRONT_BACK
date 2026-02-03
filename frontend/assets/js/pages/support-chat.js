document.getElementById('chat-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('msg-input');
    const text = input.value.trim();
    if (!text) return;

    addMsg(text, 'sent');
    input.value = '';

    const typingId = 'typing-' + Date.now();
    addMsg('...', 'received', typingId);

    try {
        const res = await ApiService.post('/assistant/chat/', { message: text });

        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        if (res.reply) {
            addMsg(res.reply, 'received');
        } else {
            addMsg("I'm not sure how to respond to that.", 'received');
        }

    } catch (err) {
        console.error(err);
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        addMsg("Network error. Please try again.", 'received');
    }
});

function addMsg(text, type, id = null) {
    const div = document.createElement('div');
    div.className = `msg ${type}`;
    div.innerText = text;
    if (id) div.id = id;

    const box = document.getElementById('chat-box');
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}
