document.addEventListener('DOMContentLoaded', async () => {
    const id = new URLSearchParams(window.location.search).get('id');
    if (!id) return window.location.href = './orders.html';

    const loader = document.getElementById('loader');
    const content = document.getElementById('od-content');

    try {
        const order = await ApiService.get(`/orders/${id}/`);

        document.getElementById('od-id').innerText = `Order #${order.id}`;
        document.getElementById('od-date').innerText = Formatters.dateTime(order.created_at);

        const statusEl = document.getElementById('od-status');
        statusEl.innerText = order.status.replace(/_/g, ' ').toUpperCase();
        statusEl.className = `status-badge status-${order.status.toLowerCase()}`;

        const otpContainer = document.getElementById('otp-container');
        if (order.delivery_otp && ['confirmed', 'picking', 'packed', 'out_for_delivery'].includes(order.status)) {
            otpContainer.innerHTML = `
                <div class="otp-display-card">
                    <div class="mb-1 text-primary font-weight-bold">
                        <i class="fas fa-key"></i> DELIVERY OTP
                    </div>
                    <div class="otp-code">${order.delivery_otp}</div>
                    <div class="small text-muted">
                        Share this code with the rider upon delivery.
                    </div>
                </div>
            `;
        } else {
            otpContainer.innerHTML = '';
        }

        const trackBtn = document.getElementById('track-btn');
        if (['confirmed', 'picking', 'packed', 'out_for_delivery'].includes(order.status)) {
            trackBtn.href = `/track_order.html?id=${order.id}`;
            trackBtn.classList.remove('d-none');
        }

        const actionContainer = document.getElementById('action-buttons');
        if (['created', 'confirmed'].includes(order.status)) {
            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn btn-outline-danger btn-sm ml-2';
            cancelBtn.innerHTML = '<i class="fas fa-times"></i> Cancel';
            cancelBtn.onclick = () => confirmCancellation(order.id);
            actionContainer.appendChild(cancelBtn);
        }

        // ---> UPDATED LOGIC: Checking item status for Partial Cancellation display
        document.getElementById('od-items').innerHTML = order.items.map(i => {
            const isCancelled = i.status === 'cancelled';
            const rowStyle = isCancelled ? 'opacity: 0.6;' : '';
            const imgStyle = `object-fit:contain; border-radius:8px; border:1px solid #eee; ${isCancelled ? 'filter: grayscale(100%);' : ''}`;
            const textStrike = isCancelled ? 'text-decoration: line-through;' : '';

            return `
            <div class="item-row" style="${rowStyle}">
                <img src="${i.sku_image || 'https://via.placeholder.com/60'}" width="60" height="60" style="${imgStyle}">
                <div style="flex:1;">
                    <div class="font-weight-600" style="${textStrike}">${i.sku_name}</div>
                    <div class="text-muted small">Qty: ${i.quantity}</div>
                    ${isCancelled ? `
                        <div class="text-danger small mt-1">
                            <i class="fas fa-exclamation-circle"></i> Item Cancelled (Reason: ${i.cancel_reason || 'Out of Stock'})
                        </div>
                    ` : ''}
                </div>
                <div class="font-weight-bold" style="${textStrike}">${Formatters.currency(i.total_price)}</div>
            </div>
        `}).join('');

        document.getElementById('val-total').innerText = Formatters.currency(order.final_amount);
        const subtotal = order.items.reduce((acc, i) => acc + parseFloat(i.total_price), 0);
        document.getElementById('val-sub').innerText = Formatters.currency(subtotal);

        const deliveryFee = parseFloat(order.final_amount) - subtotal;
        document.getElementById('val-del').innerText = deliveryFee > 0 ? Formatters.currency(deliveryFee) : 'Free';

        if (order.delivery_address_json) {
            const a = order.delivery_address_json;
            document.getElementById('od-address').innerHTML = `
                <strong>${a.label || 'Home'}</strong><br>
                ${a.full_address || a.address_line || ''}<br>
                ${a.city}, ${a.pincode}`;
        }

        document.getElementById('od-payment').innerText = order.payment_method || 'Not specified';

        if (order.refund_status && order.refund_status !== 'none') {
            const refundSection = document.getElementById('refund-section');
            refundSection.classList.remove('d-none');
            document.getElementById('refund-status-text').innerText = `Status: ${order.refund_status}`;
        }

        loader.classList.add('d-none');
        content.classList.remove('d-none');

    } catch (e) {
        console.error(e);
        loader.innerHTML = '<p class="text-danger text-center">Failed to load order details</p>';
    }
});

async function confirmCancellation(orderId) {
    if (!confirm('Are you sure you want to cancel this order?')) return;

    try {
        await ApiService.post(`/orders/${orderId}/cancel/`);
        Toast.show('Order cancelled successfully', 'success');
        setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
        Toast.show('Failed to cancel order', 'error');
    }
}