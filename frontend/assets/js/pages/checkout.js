// frontend/assets/js/pages/checkout.js

let selectedAddressId = null;
let paymentMethod = 'COD';
let resolvedWarehouseId = null; // Used only for UI state, not submitted

document.addEventListener('DOMContentLoaded', async () => {
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = APP_CONFIG.ROUTES.LOGIN;
        return;
    }
    
    if (window.AppConfigService && !window.AppConfigService.isLoaded) {
        await window.AppConfigService.load();
    }

    await Promise.all([loadAddresses(), loadSummary()]);
    document.getElementById('place-order-btn').addEventListener('click', placeOrder);
    
    const deliveryCtx = JSON.parse(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT) || 'null');
    if (deliveryCtx) {
        resolveWarehouse(deliveryCtx.lat, deliveryCtx.lng, deliveryCtx.city);
    }
});

async function loadSummary() {
    try {
        const cart = await ApiService.get('/orders/cart/');
        if(!cart.items || cart.items.length === 0) {
            window.location.href = './cart.html';
            return;
        }
        
        const list = document.getElementById('mini-cart-list');
        list.innerHTML = cart.items.map(item => `
            <div class="d-flex justify-between small mb-2">
                <span>${item.sku_name} x${item.quantity}</span>
                <span>${Formatters.currency(item.total_price)}</span>
            </div>
        `).join('');

        document.getElementById('summ-subtotal').innerText = Formatters.currency(cart.total_amount);
        document.getElementById('summ-total').innerText = Formatters.currency(cart.total_amount);
    } catch(e) { console.error("Cart error", e); }
}

async function loadAddresses() {
    const container = document.getElementById('address-list');
    container.innerHTML = '<div class="loader-spinner"></div>';
    
    try {
        const res = await ApiService.get('/auth/customer/addresses/');
        const addresses = res.results || res;

        if (addresses.length === 0) {
            container.innerHTML = '<p class="text-muted">No addresses found. Add one.</p>';
            return;
        }

        container.innerHTML = addresses.map(addr => `
            <div class="address-card ${addr.is_default ? 'active' : ''}" 
                 data-id="${addr.id}"
                 data-lat="${addr.latitude}"
                 data-lng="${addr.longitude}"
                 data-city="${addr.city}"
                 onclick="selectAddress('${addr.id}', ${addr.latitude}, ${addr.longitude}, '${addr.city}', this)">
                <div class="d-flex justify-between">
                    <strong>${addr.label}</strong>
                    ${addr.is_default ? '<span class="text-success small">Default</span>' : ''}
                </div>
                <p class="text-muted small mt-1">
                    ${addr.address_line}<br>${addr.city} - ${addr.pincode}
                </p>
            </div>
        `).join('');

        const def = addresses.find(a => a.is_default) || addresses[0];
        const storedCtx = JSON.parse(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT) || 'null');
        
        let initialSelect = def;
        if (storedCtx) {
            const match = addresses.find(a => a.id == storedCtx.id);
            if (match) initialSelect = match;
            else {
                // Address in storage no longer exists or mismatch
                localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT);
                window.dispatchEvent(new CustomEvent(APP_CONFIG.EVENTS.LOCATION_CHANGED, { detail: { source: 'ADDRESS_CLEANUP' } }));
            }
        }

        if (initialSelect) {
            const defEl = container.querySelector(`.address-card[data-id="${initialSelect.id}"]`);
            if (defEl) {
                document.querySelectorAll('.address-card').forEach(c => c.classList.remove('active'));
                defEl.classList.add('active');
                updateContextAndResolve(initialSelect.id, initialSelect.latitude, initialSelect.longitude, initialSelect.city, defEl);
            }
        }

    } catch (e) {
        container.innerHTML = '<p class="text-danger">Failed to load addresses</p>';
    }
}

window.selectAddress = function(id, lat, lng, city, el) {
    document.querySelectorAll('.address-card').forEach(c => c.classList.remove('active'));
    if (el) el.classList.add('active');
    updateContextAndResolve(id, lat, lng, city, el);
};

function updateContextAndResolve(id, lat, lng, city, el) {
    selectedAddressId = id;
    let label = 'Delivery';
    let fullText = 'Selected Address';
    if (el) {
        label = el.querySelector('strong').innerText;
        const p = el.querySelector('p');
        if(p) fullText = p.innerText.split('\n')[0];
    }
    
    // Update Global Location Manager for L2 Context
    if (window.LocationManager) {
        window.LocationManager.setDeliveryAddress({
            id: id, label: label, address_line: fullText, city: city, latitude: lat, longitude: lng
        });
    }
    resolveWarehouse(lat, lng, city);
}

window.selectPayment = function(method, el) {
    paymentMethod = method;
    document.querySelectorAll('.payment-option').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
}

// UI Check ONLY. Does not affect backend validity.
async function resolveWarehouse(lat, lng, city) {
    const placeOrderBtn = document.getElementById('place-order-btn');
    placeOrderBtn.disabled = true;
    placeOrderBtn.innerText = "Checking Availability...";

    try {
        const res = await ApiService.post('/warehouse/find-serviceable/', { latitude: lat, longitude: lng, city: city || 'Bengaluru' });

        if (res.serviceable && res.warehouse && res.warehouse.id) {
            resolvedWarehouseId = res.warehouse.id; 
            // Note: We do NOT rely on local storage for warehouse ID in checkout anymore
            placeOrderBtn.disabled = false;
            placeOrderBtn.innerText = "Place Order";
        } else {
            resolvedWarehouseId = null;
            placeOrderBtn.innerText = "Location Not Serviceable";
            Toast.error("Sorry, we do not deliver to this location yet.");
        }
    } catch (e) {
        resolvedWarehouseId = null;
        placeOrderBtn.innerText = "Service Error";
        console.error("Warehouse check error", e);
    }
}

// --- STRICT PLACE ORDER LOGIC ---
async function placeOrder() {
    if (!selectedAddressId) {
        Toast.warning("⚠️ Delivery Address is Required!");
        const stepHeader = document.querySelector('.step-header');
        if(stepHeader) stepHeader.scrollIntoView({behavior: "smooth"});
        return;
    }
    
    // Check warehouse logic (from your existing code)
    if (!resolvedWarehouseId) return Toast.error("Service check failed. Please refresh.");

    const btn = document.getElementById('place-order-btn');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

    try {
        // Step A: Create the Order first (Status: Created, Payment: Pending)
        const orderPayload = {
            delivery_address_id: selectedAddressId, 
            payment_method: paymentMethod,
            delivery_type: 'express'
        };

        const orderRes = await ApiService.post('/orders/create/', orderPayload);
        const orderId = orderRes.order ? orderRes.order.id : orderRes.id;

        // Step B: Handle Payment based on Method
        if (paymentMethod === 'COD') {
            // Direct Success for COD
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT);
            window.location.href = `/success.html?order_id=${orderId}`;
        
        } else if (paymentMethod === 'RAZORPAY') {
            // Load SDK if not present
            if (typeof Razorpay === 'undefined') await loadRazorpayScript();

            btn.innerText = "Contacting Bank...";
            
            // Call the Payment View you created explicitly to get Razorpay ID
            const paymentConfig = await ApiService.post(`/payments/create/${orderId}/`);
            
            // Launch UPI Modal
            handleRazorpay(paymentConfig, orderId, btn);
        }

    } catch (e) {
        console.error(e);
        let msg = e.message || "Order creation failed";
        Toast.error(msg);
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

function showAvailabilityErrorModal(items) {
    const itemNames = items.map(i => `<li><strong>${i.product_name}</strong> <span class="text-danger small">(${i.reason})</span></li>`).join('');
    const div = document.createElement('div');
    div.id = 'stock-error-modal';
    div.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px);`;
    div.innerHTML = `
        <div style="background:white;padding:25px;border-radius:12px;max-width:350px;width:90%;text-align:center;">
            <div style="color:#e74c3c;font-size:40px;margin-bottom:10px;"><i class="fas fa-exclamation-circle"></i></div>
            <h3>Items Unavailable</h3>
            <p class="text-muted">The following items are not available at your delivery location:</p>
            <ul style="text-align:left;background:#fff5f5;padding:15px;list-style:disc;margin:15px 0;border-radius:8px;color:#c0392b;">${itemNames}</ul>
            <button onclick="window.location.href='./cart.html'" class="btn btn-primary w-100 mb-2">Go to Cart & Remove</button>
            <button onclick="document.getElementById('stock-error-modal').remove()" class="btn btn-outline-secondary w-100">Change Address</button>
        </div>`;
    document.body.appendChild(div);
}

function handleRazorpay(rpConfig, orderId, btn) {
    if (!window.Razorpay) { 
        Toast.error("Payment SDK not loaded"); 
        btn.disabled = false;
        btn.innerText = "Place Order";
        return; 
    }

    const options = {
        "key": rpConfig.key, 
        "amount": rpConfig.amount, 
        "currency": rpConfig.currency,
        "name": rpConfig.name || "QuickDash",
        "description": rpConfig.description || "Food Order",
        "order_id": rpConfig.id, // The ID from backend (starts with order_...)
        
        // --- THIS CONFIG BLOCK RESTRICTS TO UPI ONLY ---
        "config": {
            "display": {
                "blocks": {
                    "upi": {
                        "name": "Pay via UPI",
                        "instruments": [
                            { "method": "upi" }
                        ]
                    }
                },
                "sequence": ["block.upi"],
                "preferences": {
                    "show_default_blocks": false 
                }
            }
        },
        // ------------------------------------------------

        "handler": async function (response) {
            btn.innerHTML = '<i class="fas fa-shield-alt"></i> Verifying...';
            try {
                // Verify Signature on Backend
                await ApiService.post('/payments/verify/razorpay/', {
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_signature: response.razorpay_signature
                });
                
                // Success!
                localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT);
                window.location.href = `/success.html?order_id=${orderId}`;
                
            } catch (e) {
                console.error(e);
                Toast.error("Payment successful but verification failed. Please check 'My Orders'.");
                setTimeout(() => { window.location.href = './orders.html'; }, 2000);
            }
        },
        "modal": { 
            "ondismiss": function() { 
                btn.disabled = false; 
                btn.innerText = "Place Order";
                Toast.info("Payment cancelled. You can retry.");
            } 
        },
        "theme": {
            "color": "#10b981" // Primary Green Color
        }
    };

    const rzp1 = new Razorpay(options);
    
    // Handle failures gracefully
    rzp1.on('payment.failed', function (response){
        console.error(response.error);
        Toast.error(response.error.description || "Payment Failed");
        btn.disabled = false;
        btn.innerText = "Retry Payment";
    });

    rzp1.open();
}