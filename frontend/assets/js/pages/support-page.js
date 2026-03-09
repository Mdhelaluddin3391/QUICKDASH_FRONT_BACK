document.addEventListener('DOMContentLoaded', async () => {
    const orderSelect = document.getElementById('ticket-order');
    loadTicketHistory(); // Load history

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
            orderSelect.innerHTML = '<option value="">Select an order</option>' +
                orders.map(o => `<option value="${o.id}">Order #${o.id.substring(0, 8).toUpperCase()} (${Formatters.date(o.created_at)})</option>`).join('');
        }
    } catch (e) { orderSelect.innerHTML = '<option value="">Error loading orders</option>'; }
});

document.getElementById('ticket-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submit-ticket-btn');
    const originalText = btn.innerText;

    const payload = {
        order_id: document.getElementById('ticket-order').value,
        issue_type: document.getElementById('ticket-issue').value,
        description: document.getElementById('ticket-desc').value
    };

    if (!payload.order_id) return Toast.warning("Please select an order");

    btn.disabled = true;
    btn.innerText = "Submitting...";

    try {
        await ApiService.post('/auth/customer/tickets/', payload);
        Toast.success("Ticket raised successfully!");
        e.target.reset();
        loadTicketHistory(); // Refresh list
    } catch (err) {
        Toast.error(err.message || "Failed to submit ticket");
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
});

async function loadTicketHistory() {
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) return;
    const container = document.getElementById('ticket-list');
    const section = document.getElementById('history-section');

    try {
        const res = await ApiService.get('/auth/customer/tickets/history/');
        const tickets = res.results || res;

        if (tickets.length > 0) {
            section.style.display = 'block';
            container.innerHTML = tickets.map(t => `
                    <div class="card p-3">
                        <div class="d-flex justify-between align-center mb-2">
                            <span class="badge ${t.status === 'resolved' ? 'status-delivered' : 'status-pending'}">${t.status.toUpperCase()}</span>
                            <small class="text-muted">${Formatters.date(t.created_at)}</small>
                        </div>
                        <h5 class="m-0">Issue: ${t.issue_type.replace('_', ' ')}</h5>
                        <p class="text-muted small mt-1">Order #${t.order_id}</p>
                        <p class="mt-2 text-dark">${t.description}</p>
                        ${t.resolution ? `<div class="mt-2 p-2 bg-light small"><strong>Resolution:</strong> ${t.resolution}</div>` : ''}
                    </div>
                `).join('');
        }
    } catch (e) { console.warn("Failed to load tickets", e); }
}
