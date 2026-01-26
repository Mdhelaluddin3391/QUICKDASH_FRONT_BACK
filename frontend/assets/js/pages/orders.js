// frontend/assets/js/pages/orders.js

document.addEventListener('DOMContentLoaded', async () => {
    // Auth Check
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = APP_CONFIG.ROUTES.LOGIN;
        return;
    }

    await loadOrderHistory();
});

async function loadOrderHistory() {
    const container = document.getElementById('orders-list-container');
    container.innerHTML = '<div class="loader-spinner"></div>';

    try {
        const res = await ApiService.get('/orders/my-orders/');
        const orders = res.results || res;

        if (orders.length === 0) {
            container.innerHTML = `
                <div class="empty-state text-center py-5">
                    <img src="/assets/images/no-orders.png" style="width:100px; opacity:0.5;">
                    <h5 class="mt-3">No orders yet</h5>
                    <p class="text-muted">Start shopping to see your orders here.</p>
                    <a href="/" class="btn btn-primary">Start Shopping</a>
                </div>`;
            return;
        }

        container.innerHTML = orders.map(order => createOrderCard(order)).join('');

    } catch (e) {
        console.error("Order History Error", e);
        container.innerHTML = `<p class="text-danger text-center">Failed to load orders.</p>`;
    }
}

function createOrderCard(order) {
    // Status Badge Logic
    const statusColors = {
        'created': 'secondary',
        'confirmed': 'info',
        'picking': 'info',
        'packed': 'warning',
        'out_for_delivery': 'primary',
        'delivered': 'success',
        'cancelled': 'danger'
    };
    const badgeColor = statusColors[order.status] || 'secondary';
    const isActive = ['created', 'confirmed', 'picking', 'packed', 'out_for_delivery'].includes(order.status);

    // Format Date
    const date = new Date(order.created_at).toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });

    // OTP Badge (If available in list view)
    const otpBadge = order.delivery_otp 
        ? `<div class="mt-2 px-2 py-1 bg-light border border-info rounded text-center text-primary font-weight-bold" style="font-size: 0.9em;">
             📦 OTP: ${order.delivery_otp}
           </div>`
        : '';

    return `
        <div class="card mb-3 order-card shadow-sm">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <div>
                        <h6 class="mb-0 font-weight-bold">Order #${order.id}</h6>
                        <small class="text-muted">${date}</small>
                    </div>
                    <span class="badge badge-${badgeColor}">${formatStatus(order.status)}</span>
                </div>
                
                <div class="d-flex justify-content-between align-items-center">
                    <div class="text-muted small">
                        ${order.item_count} Items | Total: <strong class="text-dark">${Formatters.currency(order.final_amount)}</strong>
                    </div>
                </div>

                ${otpBadge}

                <hr class="my-2">

                <div class="d-flex justify-content-end">
                    ${isActive ? 
                        `<a href="/track_order.html?id=${order.id}" class="btn btn-sm btn-primary">
                            <i class="fas fa-map-marker-alt"></i> Track Order
                        </a>` : 
                        `<button onclick="reorder(${order.id})" class="btn btn-sm btn-outline-secondary">
                            <i class="fas fa-redo"></i> Reorder
                        </button>`
                    }
                    <a href="/order_detail.html?id=${order.id}" class="btn btn-sm btn-link text-muted ml-2">Details ></a>
                </div>
            </div>
        </div>
    `;
}

function formatStatus(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

window.reorder = async function(orderId) {
    if(!confirm("Add items from this order to your cart?")) return;
    
    try {
        // Fetch details to get items
        const order = await ApiService.get(`/orders/${orderId}/`);
        
        let addedCount = 0;
        for (const item of order.items) {
            try {
                await CartService.addItem(item.sku, item.quantity);
                addedCount++;
            } catch (e) {
                console.warn(`Skipped item ${item.sku}:`, e.message);
            }
        }
        
        if (addedCount > 0) {
            Toast.success(`${addedCount} items added to cart`);
            window.location.href = '/cart.html';
        } else {
            Toast.warning("Items are currently out of stock");
        }

    } catch (e) {
        Toast.error("Failed to reorder");
    }
};