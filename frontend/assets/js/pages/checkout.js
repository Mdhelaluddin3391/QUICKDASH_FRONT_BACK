// frontend/assets/js/pages/checkout.js

let selectedAddressId = null;
let paymentMethod = 'COD';
let resolvedWarehouseId = null; // Used only for UI state, not submitted

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Auth Check
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = APP_CONFIG.ROUTES.LOGIN;
        return;
    }
    
    // 2. Config Load
    if (window.AppConfigService && !window.AppConfigService.isLoaded) {
        await window.AppConfigService.load();
    }

    // 3. Initial Data Load
    await Promise.all([loadAddresses(), loadSummary()]);
    
    // 4. Order Button Listener
    const placeOrderBtn = document.getElementById('place-order-btn');
    if(placeOrderBtn) {
        placeOrderBtn.addEventListener('click', placeOrder);
    }
    
    // 5. Restore Context (Serviceability Check)
    const deliveryCtx = JSON.parse(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT) || 'null');
    if (deliveryCtx) {
        resolveWarehouse(deliveryCtx.lat, deliveryCtx.lng, deliveryCtx.city);
    }

    // 6. Address Form Submit Listener (The FIX)
    const addrForm = document.getElementById('address-form');
    if (addrForm) {
        addrForm.addEventListener('submit', handleSaveAddress);
    }
});

// ==========================================
//  NEW: MAP & ADDRESS MODAL LOGIC (The Fix)
// ==========================================

// 1. "Add New Address" button click logic
window.openAddressModal = function() {
    if (window.LocationPicker) {
        // Map Picker open karein
        window.LocationPicker.open((data) => {
            // Jab user location confirm kare, form bharein
            showAddressFormModal(data);
        });
    } else {
        Toast.error("Map service loading... please wait.");
    }
};

// 2. Map data se Form fill karna
function showAddressFormModal(mapData) {
    const modal = document.getElementById('address-modal');
    if(modal) modal.classList.remove('d-none');

    document.getElementById('address-form').reset();

    // Hidden Fields
    document.getElementById('addr-lat').value = mapData.lat;
    document.getElementById('addr-lng').value = mapData.lng;
    document.getElementById('addr-google-text').value = mapData.address;

    // Display
    document.getElementById('display-map-address').innerText = mapData.address || "Pinned Location";

    // Auto-fill Fields
    document.getElementById('addr-city').value = mapData.city || '';
    document.getElementById('addr-pin').value = mapData.pincode || '';

    if (mapData.houseNo) {
        document.getElementById('addr-house').value = mapData.houseNo;
    }

    let buildingInfo = [];
    if (mapData.building) buildingInfo.push(mapData.building);
    if (mapData.area) buildingInfo.push(mapData.area);
    if (buildingInfo.length > 0) {
        document.getElementById('addr-building').value = buildingInfo.join(', ');
    }

    // User Info Auto-fill
    try {
        const user = JSON.parse(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.USER) || '{}');
        if (user.first_name || user.last_name) {
            document.getElementById('addr-name').value = `${user.first_name || ''} ${user.last_name || ''}`.trim();
        }
        if (user.phone) {
            document.getElementById('addr-phone').value = user.phone;
        }
    } catch (e) {
        console.warn("User data missing for auto-fill");
    }
}

// 3. Close Modal
window.closeAddressModal = function() {
    const modal = document.getElementById('address-modal');
    if(modal) modal.classList.add('d-none');
};

// 4. Address Save Logic (with Fixes)
async function handleSaveAddress(e) {
    e.preventDefault();
    
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Verifying...";

    try {
        const lat = document.getElementById('addr-lat').value;
        const lng = document.getElementById('addr-lng').value;

        // --- FIX 1: Serviceability Check ---
        const checkRes = await ApiService.post('/warehouse/find-serviceable/', { latitude: lat, longitude: lng });
        
        if (!checkRes.serviceable) {
            Toast.warning("Location currently unserviceable, but address will be saved.");
        }

        btn.innerText = "Saving...";

        const payload = {
            label: document.querySelector('input[name="addr-type"]:checked').value,
            receiver_name: document.getElementById('addr-name').value,
            receiver_phone: document.getElementById('addr-phone').value,
            house_no: document.getElementById('addr-house').value,
            floor_no: document.getElementById('addr-floor').value,
            apartment_name: document.getElementById('addr-building').value,
            landmark: document.getElementById('addr-landmark').value,
            
            // --- FIX 2: Correct Field Name for Backend ---
            google_address_text: document.getElementById('addr-google-text').value,
            
            city: document.getElementById('addr-city').value,
            pincode: document.getElementById('addr-pin').value,
            latitude: lat,
            longitude: lng,
            is_default: true
        };

        await ApiService.post('/auth/customer/addresses/', payload);
        
        Toast.success("Address Saved!");
        closeAddressModal();
        loadAddresses(); // Refresh list
    } catch (error) {
        console.error("Save error:", error);
        let msg = error.message || "Failed to save address";
        if (error.data && error.data.error && error.data.error.details) {
             msg = JSON.stringify(error.data.error.details);
        }
        Toast.error(msg);
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
    } catch(e) { console.error("Cart load error", e); }
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
                    ${addr.address_line || addr.google_address_text}<br>${addr.city} - ${addr.pincode}
                </p>
            </div>
        `).join('');

        // Auto-select Default
        const def = addresses.find(a => a.is_default) || addresses[0];
        const storedCtx = JSON.parse(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT) || 'null');
        
        let initialSelect = def;
        // Agar context mein purana address saved hai toh wo use karein
        if (storedCtx) {
            const match = addresses.find(a => a.id == storedCtx.id);
            if (match) initialSelect = match;
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
    
    // Global Manager update (Serviceability Check ke liye zaroori hai)
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
        const res = await ApiService.post('/warehouse/find-serviceable/', { latitude: lat, longitude: lng, city: city });

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
        return;
    }
    
    if (!resolvedWarehouseId) return Toast.error("Service check failed. Please refresh.");

    const btn = document.getElementById('place-order-btn');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

    try {
        // Get cart total
        const cart = await ApiService.get('/orders/cart/');
        if (!cart || !cart.total_amount) {
            throw new Error("Unable to get cart total");
        }

        const orderPayload = {
            delivery_address_id: selectedAddressId, 
            payment_method: paymentMethod,
            delivery_type: 'express',
            total_amount: cart.total_amount
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

// Helper to load Razorpay if not present
function loadRazorpayScript() {
    return new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = 'https://checkout.razorpay.com/v1/checkout.js';
        script.onload = () => resolve(true);
        script.onerror = () => resolve(false);
        document.body.appendChild(script);
    });
}