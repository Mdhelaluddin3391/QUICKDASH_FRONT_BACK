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
    if (!container) return; // Fail safe
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
    // 1. Status & Active Check
    const s = (order.status || 'created').toLowerCase();
    let badgeClass = 'processing';
    let iconClass = 'fa-box-open';
    
    if (s === 'delivered') { badgeClass = 'delivered'; iconClass = 'fa-check-circle'; }
    else if (s === 'cancelled') { badgeClass = 'cancelled'; iconClass = 'fa-times-circle'; }
    else if (s === 'shipped' || s === 'out_for_delivery') { badgeClass = 'shipped'; iconClass = 'fa-truck'; }

    const isActive = ['created', 'confirmed', 'picking', 'packed', 'out_for_delivery'].includes(s);
    const isCancelledClass = badgeClass === 'cancelled' ? 'is-cancelled' : '';

    // 2. Format Date
    const date = new Date(order.created_at).toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });

    // 3. OTP Badge
    const otpBadge = order.delivery_otp && isActive
        ? `<div style="display:inline-block; margin-top:8px; padding: 4px 10px; background: #f0fdf4; border: 1px dashed #fdba74; border-radius: 6px; color: #c2410c; font-weight: bold; font-size: 0.85rem; letter-spacing: 1px;">
             <i class="fas fa-key"></i> OTP: ${order.delivery_otp}
           </div>`
        : '';

    // 4. Partial Cancel Badge Logic
    let partialCancelBadge = '';
    if (s !== 'cancelled' && order.items) {
        const hasCancelledItems = order.items.some(item => item.status === 'cancelled' || item.is_cancelled);
        if (hasCancelledItems) {
            partialCancelBadge = `<div style="font-size: 0.75rem; color: #9a3412; background: #ffedd5; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 4px;"><i class="fas fa-exclamation-triangle"></i> Partial items cancelled</div>`;
        }
    }

    // 5. Render HTML
    return `
        <div class="order-card-pro ${isCancelledClass}">
            <div class="order-card-header">
                <div class="order-id-pro">
                    <i class="fas fa-shopping-bag text-primary"></i> 
                    Order #${order.id}
                </div>
                <div class="status-badge ${badgeClass}">
                    <i class="fas ${iconClass}"></i> ${formatStatus(order.status)}
                </div>
            </div>
            
            <div class="order-card-body align-items-start">
                <div class="order-details-summary">
                    <span class="order-date-pro"><i class="far fa-clock"></i> ${date}</span>
                    <span class="order-items-count">${order.item_count || 1} Item(s)</span>
                    ${partialCancelBadge}
                    ${otpBadge}
                </div>
                <div class="order-total-pro">
                    ${window.Formatters ? Formatters.currency(order.final_amount || order.total_amount) : `₹${order.final_amount}`}
                </div>
            </div>

            <div class="order-card-footer mt-3" style="border-top: 1px solid #f1f5f9; padding-top: 12px; justify-content: flex-end; display: flex; gap: 10px;">
                ${isActive ? 
                    `<button onclick="window.location.href='/track_order.html?id=${order.id}'" class="btn-view-details" style="background: #eff6ff; color: #0ea5e9; border-color: #bae6fd;">
                        <i class="fas fa-map-marker-alt"></i> Track
                    </button>` : 
                    `<button onclick="reorder(${order.id})" class="btn-view-details" style="background: #fff; color: #64748b; border-color: #e2e8f0;">
                        <i class="fas fa-redo"></i> Reorder
                    </button>`
                }
                <button onclick="window.location.href='/order_detail.html?id=${order.id}'" class="btn-view-details" style="background: #0f172a; color: #fff; border-color: #0f172a;">
                    Details <i class="fas fa-arrow-right" style="font-size:0.8em; margin-left:4px;"></i>
                </button>
            </div>
        </div>
    `;
}

function formatStatus(status) {
    if (!status) return 'Pending';
    return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

window.reorder = async function(orderId) {
    if(!confirm("Add items from this order to your cart?")) return;
    
    try {
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
            if(window.Toast) Toast.success(`${addedCount} items added to cart`);
            window.location.href = '/cart.html';
        } else {
            if(window.Toast) Toast.warning("Items are currently out of stock");
        }

    } catch (e) {
        if(window.Toast) Toast.error("Failed to reorder");
    }
};