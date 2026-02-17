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
        const res = await window.ApiService.post('/assistant/chat/', { message: text });

        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        if (res.reply) {
            addMsg(res.reply, 'received');
        } else {
            addMsg("Mujhe iska jawab nahi pata.", 'received');
        }

        // WhatsApp Action Handling
        if (res.action === 'whatsapp_support' && res.params && res.params.url) {
            addWhatsAppButton(res.params.url);
        }

        // Action Handling for tracking
        if (res.action === 'track_order' && res.params && res.params.order_id) {
            addActionButton('Track Order Now', `/track_order.html?id=${res.params.order_id}`);
        }

        if (res.action === 'view_orders') {
            addActionButton('View All Orders', '/orders.html');
        }

    } catch (err) {
        console.error(err);
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        addMsg("Network error. Kripya dobara koshish karein.", 'received');
    }
});

function addMsg(text, type, id = null) {
    const div = document.createElement('div');
    div.className = `msg ${type}`;
    div.innerText = text; // innerText avoids XSS attacks
    if (id) div.id = id;

    const box = document.getElementById('chat-box');
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

// Custom Function to Add WhatsApp Button
function addWhatsAppButton(url) {
    const div = document.createElement('div');
    div.className = "msg received";
    div.style.backgroundColor = "transparent"; 
    div.style.padding = "0";

    const btn = document.createElement('a');
    btn.href = url;
    btn.target = "_blank";
    btn.innerHTML = '<i class="fab fa-whatsapp"></i> Chat on WhatsApp';
    
    // Inline styling for the button (Aap isko apne CSS me bhi daal sakte hain)
    btn.style.display = "inline-block";
    btn.style.backgroundColor = "#25d366";
    btn.style.color = "white";
    btn.style.padding = "10px 20px";
    btn.style.borderRadius = "8px";
    btn.style.textDecoration = "none";
    btn.style.fontWeight = "bold";
    btn.style.marginTop = "5px";

    div.appendChild(btn);
    const box = document.getElementById('chat-box');
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

// Custom Function to Add General Action Buttons (Track Order, etc)
function addActionButton(text, url) {
    const div = document.createElement('div');
    div.className = "msg received";
    div.style.backgroundColor = "transparent"; 
    div.style.padding = "0";

    const btn = document.createElement('a');
    btn.href = url;
    btn.innerHTML = text;
    
    btn.style.display = "inline-block";
    btn.style.backgroundColor = "var(--primary, #007bff)";
    btn.style.color = "white";
    btn.style.padding = "8px 15px";
    btn.style.borderRadius = "5px";
    btn.style.textDecoration = "none";
    btn.style.marginTop = "5px";

    div.appendChild(btn);
    const box = document.getElementById('chat-box');
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}