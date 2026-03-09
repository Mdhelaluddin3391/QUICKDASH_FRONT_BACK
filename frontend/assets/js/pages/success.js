document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('order_id');

    if (orderId) {
        const displayId = orderId.length > 8 ? orderId.substring(0, 8).toUpperCase() : orderId;
        document.getElementById('display-order-id').innerText = `Order #${displayId}`;
    }
});
