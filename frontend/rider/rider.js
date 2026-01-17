// frontend/rider/rider.js

let map, directionsService, directionsRenderer;
let currentDelivery = null;
let watchId = null;
let isOnline = false;

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Auth Check
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = 'login.html';
        return;
    }

    // 2. Load Maps
    try {
        await window.MapsLoader.load();
        initMap();
        await fetchProfile();
        startJobPolling();
    } catch (e) {
        alert("Map load failed. Check internet.");
    }
});

function initMap() {
    map = new google.maps.Map(document.getElementById("map"), {
        zoom: 15,
        center: { lat: 12.9716, lng: 77.5946 }, // Default
        disableDefaultUI: true,
    });

    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer({ map: map });

    // Track Rider Location
    if (navigator.geolocation) {
        watchId = navigator.geolocation.watchPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lng = pos.coords.longitude;
                const me = { lat, lng };
                
                // Center map on rider initially
                if(!currentDelivery) map.setCenter(me);

                // Send Ping to Backend if active order
                if (currentDelivery) {
                    pingLocation(lat, lng);
                }
            },
            (err) => console.warn("GPS Error", err),
            { enableHighAccuracy: true }
        );
    }
}

// --- API Calls ---

async function fetchProfile() {
    try {
        const res = await ApiService.get('/riders/me/');
        isOnline = res.is_available;
        updateStatusUI();
    } catch (e) {
        console.error(e);
    }
}

async function toggleStatus() {
    try {
        const newState = !isOnline;
        await ApiService.post('/riders/availability/', { is_available: newState });
        isOnline = newState;
        updateStatusUI();
        if (isOnline) checkForOrders();
    } catch (e) {
        alert("Cannot change status: " + (e.message || "Error"));
    }
}

function updateStatusUI() {
    const el = document.getElementById('status-toggle');
    if (isOnline) {
        el.className = 'online-toggle on';
        el.innerHTML = '<i class="fas fa-toggle-on"></i> You are ONLINE';
    } else {
        el.className = 'online-toggle';
        el.innerHTML = '<i class="fas fa-toggle-off"></i> You are OFFLINE';
    }
}

async function checkForOrders() {
    if (!isOnline) return;

    try {
        // Fetch active deliveries
        const deliveries = await ApiService.get('/delivery/me/');
        // Filter for active ones
        const active = deliveries.find(d => ['assigned', 'picked_up', 'out_for_delivery'].includes(d.status));

        if (active) {
            renderActiveOrder(active);
        } else {
            renderIdle();
        }
    } catch (e) {
        console.error("Polling error", e);
    }
}

function startJobPolling() {
    checkForOrders();
    setInterval(checkForOrders, 10000); // Check every 10 seconds
}

// --- Order Rendering ---

function renderIdle() {
    currentDelivery = null;
    document.getElementById('idle-state').classList.remove('hidden');
    document.getElementById('active-order').classList.add('hidden');
    if (directionsRenderer) directionsRenderer.setDirections({ routes: [] }); // Clear map path
}

function renderActiveOrder(delivery) {
    if (currentDelivery && currentDelivery.id === delivery.id && currentDelivery.status === delivery.status) return; // No change
    
    currentDelivery = delivery;
    const order = delivery.order;
    const address = order.delivery_address_json;

    document.getElementById('idle-state').classList.add('hidden');
    const panel = document.getElementById('active-order');
    panel.classList.remove('hidden');

    document.getElementById('order-id').innerText = order.id;
    document.getElementById('cust-name').innerText = `Customer: ${order.user || 'Guest'}`; // Adjust based on serializer
    document.getElementById('cust-address').innerText = address.full_address || address.address_line;
    
    // COD Logic
    const codEl = document.getElementById('cod-amount');
    if (order.payment_method === 'COD' && order.payment_status !== 'PAID') {
        codEl.innerText = Formatters.currency(order.final_amount);
        codEl.parentElement.style.display = 'flex';
    } else {
        codEl.parentElement.style.display = 'none';
    }

    // Action Buttons based on Status
    const actions = document.getElementById('action-buttons');
    actions.innerHTML = '';

    if (delivery.status === 'assigned') {
        actions.innerHTML = `<button onclick="acceptOrder(${delivery.id})" class="btn-action btn-go">Start Delivery</button>`;
    } else if (delivery.status === 'picked_up' || delivery.status === 'out_for_delivery') {
        // Draw Route
        drawRoute(address.lat, address.lng);
        actions.innerHTML = `
            <a href="https://www.google.com/maps/dir/?api=1&destination=${address.lat},${address.lng}" target="_blank" class="btn-action btn-go" style="display:block; text-align:center; text-decoration:none; margin-bottom:10px;">
                <i class="fas fa-location-arrow"></i> Navigate
            </a>
            <button onclick="openOtpModal()" class="btn-action btn-done">Complete Delivery</button>
        `;
    }
}

// --- Map Logic ---

function drawRoute(destLat, destLng) {
    if (!navigator.geolocation) return;
    
    navigator.geolocation.getCurrentPosition(pos => {
        const origin = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        const dest = { lat: parseFloat(destLat), lng: parseFloat(destLng) };

        directionsService.route({
            origin: origin,
            destination: dest,
            travelMode: google.maps.TravelMode.DRIVING
        }, (response, status) => {
            if (status === "OK") {
                directionsRenderer.setDirections(response);
            }
        });
    });
}

function pingLocation(lat, lng) {
    if (!currentDelivery) return;
    // Fire and forget
    ApiService.post(`/delivery/location/ping/${currentDelivery.order.id}/`, {
        latitude: lat, longitude: lng
    }).catch(() => {});
}

// --- Actions ---

window.acceptOrder = async (id) => {
    if(!confirm("Accept this order?")) return;
    try {
        await ApiService.post(`/delivery/${id}/respond/`, { action: 'accept' });
        // Simulating Pick Up immediately for MVP simplicity
        // In real world, they would scan a QR code at warehouse
        // For now, let's assume they are at warehouse and 'Verify Handover'
        await ApiService.post(`/delivery/handover/verify/`, { order_id: currentDelivery.order.id });
        checkForOrders();
    } catch (e) {
        alert("Error: " + e.message);
    }
};

window.openOtpModal = () => {
    document.getElementById('otp-modal').style.display = 'flex';
    document.getElementById('delivery-otp').value = '';
    document.getElementById('delivery-otp').focus();
};

window.completeOrder = async () => {
    const otp = document.getElementById('delivery-otp').value;
    if (otp.length !== 6) { alert("Enter valid 6-digit OTP"); return; }

    try {
        await ApiService.post(`/delivery/${currentDelivery.id}/complete/`, { otp: otp });
        document.getElementById('otp-modal').style.display = 'none';
        alert("Order Delivered Successfully! Great Job! 🚀");
        renderIdle();
        checkForOrders();
    } catch (e) {
        alert("Failed: " + e.message);
    }
};