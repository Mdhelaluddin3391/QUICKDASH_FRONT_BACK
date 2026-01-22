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
    
    const placeOrderBtn = document.getElementById('place-order-btn');
    if(placeOrderBtn) {
        placeOrderBtn.addEventListener('click', placeOrder);
    }
    
    const deliveryCtx = JSON.parse(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT) || 'null');
    if (deliveryCtx) {
        resolveWarehouse(deliveryCtx.lat, deliveryCtx.lng, deliveryCtx.city);
    }

    // --- NEW: Address Form Submit Listener Add Karein ---
    const addrForm = document.getElementById('address-form');
    if (addrForm) {
        addrForm.addEventListener('submit', handleSaveAddress);
    }
});

// ==========================================
//  NEW: MAP & ADDRESS MODAL LOGIC
// ==========================================

// 1. "Add New Address" button click hone par ye chalega
window.openAddressModal = function() {
    if (window.LocationPicker) {
        // Pehle Map Picker open karein
        window.LocationPicker.open((data) => {
            // Jab user Map par location confirm karega, ye data milega
            showAddressFormModal(data);
        });
    } else {
        Toast.error("Map service loading... please wait.");
    }
};

// 2. Map se data lekar Form show karna
function showAddressFormModal(mapData) {
    const modal = document.getElementById('address-modal');
    if(modal) modal.classList.remove('d-none');

    // Form reset karein
    document.getElementById('address-form').reset();

    // 1. Hidden Fields (Coordinates & Google Text)
    document.getElementById('addr-lat').value = mapData.lat;
    document.getElementById('addr-lng').value = mapData.lng;
    document.getElementById('addr-google-text').value = mapData.address;

    // 2. Display Label
    document.getElementById('display-map-address').innerText = mapData.address || "Pinned Location";

    // 3. AUTO-FILL LOGIC
    // City & Pincode
    document.getElementById('addr-city').value = mapData.city || '';
    document.getElementById('addr-pin').value = mapData.pincode || '';

    // House No (Agar map ne pakda hai toh)
    if (mapData.houseNo) {
        document.getElementById('addr-house').value = mapData.houseNo;
    }

    // Building/Apartment Name
    let buildingInfo = [];
    if (mapData.building) buildingInfo.push(mapData.building);
    if (mapData.area) buildingInfo.push(mapData.area);
    
    if (buildingInfo.length > 0) {
        document.getElementById('addr-building').value = buildingInfo.join(', ');
    }

    // 4. User Personal Details (LocalStorage se)
    try {
        const user = JSON.parse(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.USER) || '{}');
        // Name Auto-fill
        if (user.first_name || user.last_name) {
            document.getElementById('addr-name').value = `${user.first_name || ''} ${user.last_name || ''}`.trim();
        }
        // Phone Auto-fill
        if (user.phone) {
            document.getElementById('addr-phone').value = user.phone;
        }
    } catch (e) {
        console.warn("User data not found for auto-fill");
    }
}

// 3. Modal Close
window.closeAddressModal = function() {
    const modal = document.getElementById('address-modal');
    if(modal) modal.classList.add('d-none');
};

// 4. API Call karke Address Save karna
async function handleSaveAddress(e) {
    e.preventDefault();
    
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Saving...";

    try {
        const payload = {
            label: document.querySelector('input[name="addr-type"]:checked').value,
            receiver_name: document.getElementById('addr-name').value,
            receiver_phone: document.getElementById('addr-phone').value,
            house_no: document.getElementById('addr-house').value,
            floor_no: document.getElementById('addr-floor').value,
            apartment_name: document.getElementById('addr-building').value,
            landmark: document.getElementById('addr-landmark').value,
            address_line: document.getElementById('addr-google-text').value,
            city: document.getElementById('addr-city').value,
            pincode: document.getElementById('addr-pin').value,
            latitude: document.getElementById('addr-lat').value,
            longitude: document.getElementById('addr-lng').value,
            is_default: true
        };

        // Backend API call
        await ApiService.post('/auth/customer/addresses/', payload);
        
        Toast.success("Address Saved!");
        closeAddressModal();
        loadAddresses(); // Reload the address list
    } catch (error) {
        console.error("Save address error:", error);
        Toast.error(error.message || "Failed to save address");
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

// ==========================================
//  EXISTING CHECKOUT LOGIC
// ==========================================

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

async function resolveWarehouse(lat, lng, city) {
    const placeOrderBtn = document.getElementById('place-order-btn');
    if (!placeOrderBtn) return;

    placeOrderBtn.disabled = true;
    placeOrderBtn.innerText = "Checking Availability...";

    try {
        const res = await ApiService.post('/warehouse/find-serviceable/', { latitude: lat, longitude: lng, city: city || 'Bengaluru' });

        if (res.serviceable && res.warehouse && res.warehouse.id) {
            resolvedWarehouseId = res.warehouse.id; 
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

async function placeOrder() {
    if (!selectedAddressId) {
        Toast.warning("⚠️ Delivery Address is Required!");
        const stepHeader = document.querySelector('.step-header');
        if(stepHeader) stepHeader.scrollIntoView({behavior: "smooth"});
        return;
    }
    
    if (!resolvedWarehouseId) return Toast.error("Service check failed. Please refresh.");

    const btn = document.getElementById('place-order-btn');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

    try {
        const orderPayload = {
            delivery_address_id: selectedAddressId, 
            payment_method: paymentMethod,
            delivery_type: 'express'
        };

        const orderRes = await ApiService.post('/orders/create/', orderPayload);
        const orderId = orderRes.order ? orderRes.order.id : orderRes.id;

        if (paymentMethod === 'COD') {
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT);
            window.location.href = `/success.html?order_id=${orderId}`;
        
        } else if (paymentMethod === 'RAZORPAY') {
            if (typeof Razorpay === 'undefined') await loadRazorpayScript();
            btn.innerText = "Contacting Bank...";
            const paymentConfig = await ApiService.post(`/payments/create/${orderId}/`);
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
        "order_id": rpConfig.id, 
        "config": {
            "display": {
                "blocks": {
                    "upi": {
                        "name": "Pay via UPI",
                        "instruments": [ { "method": "upi" } ]
                    }
                },
                "sequence": ["block.upi"],
                "preferences": { "show_default_blocks": false }
            }
        },
        "handler": async function (response) {
            btn.innerHTML = '<i class="fas fa-shield-alt"></i> Verifying...';
            try {
                await ApiService.post('/payments/verify/razorpay/', {
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_signature: response.razorpay_signature
                });
                localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT);
                window.location.href = `/success.html?order_id=${orderId}`;
            } catch (e) {
                console.error(e);
                Toast.error("Payment successful but verification failed.");
                setTimeout(() => { window.location.href = './orders.html'; }, 2000);
            }
        },
        "modal": { 
            "ondismiss": function() { 
                btn.disabled = false; 
                btn.innerText = "Place Order";
                Toast.info("Payment cancelled.");
            } 
        },
        "theme": { "color": "#10b981" }
    };

    const rzp1 = new Razorpay(options);
    rzp1.on('payment.failed', function (response){
        Toast.error(response.error.description || "Payment Failed");
        btn.disabled = false;
        btn.innerText = "Retry Payment";
    });
    rzp1.open();
}