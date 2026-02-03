document.addEventListener('DOMContentLoaded', async () => {
    const orderSelect = document.getElementById('ticket-order');
    loadTicketHistory();

    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        orderSelect.innerHTML = '<option value="">Login to see orders</option>';
        return;
    }

    try {
        const res = await ApiService.get('/orders/my/');
        const orders = res.results || res;
        if (orders.length === 0) {
            orderSelect.innerHTML = '<option value="">No orders found</option>';
        } else {
            const options = orders.map(o => `<option value="${o.id}">Order #${o.id} - ${Formatters.date(o.created_at)}</option>`).join('');
            orderSelect.innerHTML = '<option value="">Select an order...</option>' + options;
        }
    } catch (e) {
        orderSelect.innerHTML = '<option value="">Failed to load orders</option>';
    }
});

function loadTicketHistory() {
    const historyDiv = document.getElementById('ticket-history');
    try {
        const tickets = JSON.parse(localStorage.getItem('support_tickets') || '[]');
        if (tickets.length === 0) {
            historyDiv.innerHTML = '<p class="text-muted small">No previous tickets</p>';
            return;
        }
        historyDiv.innerHTML = tickets.map(t => `
            <div class="ticket-item p-2 border-bottom small">
                <strong>#${t.id}</strong> - ${t.subject}
                <br><span class="text-muted text-xs">${t.date}</span>
            </div>
        `).join('');
    } catch (e) {
        historyDiv.innerHTML = '';
    }
}

document.getElementById('support-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const subject = document.getElementById('ticket-subject').value;
    const message = document.getElementById('ticket-message').value;
    const orderId = document.getElementById('ticket-order').value;

    try {
        const payload = { subject, message };
        if (orderId) payload.order_id = orderId;

        const res = await ApiService.post('/support/tickets/', payload);

        Toast.show('Ticket created successfully!', 'success');

        const newTicket = {
            id: res.id,
            subject: subject,
            date: new Date().toLocaleDateString()
        };
        const tickets = JSON.parse(localStorage.getItem('support_tickets') || '[]');
        tickets.unshift(newTicket);
        localStorage.setItem('support_tickets', JSON.stringify(tickets.slice(0, 5)));

        e.target.reset();
        loadTicketHistory();
    } catch (e) {
        Toast.show('Failed to create ticket', 'error');
    }
});
