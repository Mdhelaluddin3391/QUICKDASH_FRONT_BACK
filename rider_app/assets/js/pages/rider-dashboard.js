let locationWatchId = null;
let currentActiveOrderId = null;

document.addEventListener('DOMContentLoaded', async () => {
    if (!localStorage.getItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = RIDER_CONFIG.ROUTES.LOGIN;
        return;
    }
    await initDashboard();
    setInterval(checkActiveJobs, 8000); // 8 seconds mein refresh
});

async function initDashboard() {
    try {
        const profile = await ApiService.get('/riders/me/');
        const toggle = document.getElementById('online-toggle');
        
        toggle.checked = profile.is_available;
        updateStatusUI(profile.is_available);
        
        if (profile.todays_earnings !== undefined) {
            document.getElementById('today-earnings').innerText = `₹${profile.todays_earnings}`;
        }
        await checkActiveJobs();
    } catch (e) {
        console.error("Dashboard Init Failed", e);
    }
}

function updateStatusUI(isOnline) {
    const badge = document.getElementById('rider-status');
    if (isOnline) {
        badge.innerText = "Online";
        badge.className = "badge-online";
        startLocationTracking();
    } else {
        badge.innerText = "Offline";
        badge.className = "badge-offline";
        stopLocationTracking();
    }
}

// 📍 GPS Tracking & Backend Sync
function startLocationTracking() {
    if (!navigator.geolocation) return;

    locationWatchId = navigator.geolocation.watchPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            try {
                // Agar koi order chal raha hai toh specific tracking endpoint use karein
                if (currentActiveOrderId) {
                    await ApiService.post(`/delivery/location/${currentActiveOrderId}/`, { latitude: lat, longitude: lng });
                } else {
                    await ApiService.post('/riders/location/', { lat, lng });
                }
            } catch(e) { console.warn("Location sync failed", e); }
        },
        null, { enableHighAccuracy: true, timeout: 5000 }
    );
}

async function checkActiveJobs() {
    if (!document.getElementById('online-toggle').checked) return;

    try {
        const deliveries = await ApiService.get('/delivery/me/');
        const activeJob = deliveries.find(d => ['assigned', 'picked_up', 'out_for_delivery'].includes(d.status));
        const container = document.getElementById('active-job-area');
        
        if (activeJob) {
            currentActiveOrderId = activeJob.order.id;
            renderJobCard(activeJob, container);
        } else {
            currentActiveOrderId = null;
            container.innerHTML = `<div class="no-job"><i class="fas fa-motorcycle"></i><p>Scanning for orders...</p></div>`;
        }
    } catch (e) { console.error("Job fetch error", e); }
}

function renderJobCard(job, container) {
    const order = job.order;
    const address = order.delivery_address_json || {};
    
    let actionArea = '';

    // Flow Logic based on status
    if (job.status === 'assigned') {
        // Step 1: Acceptance ya Pickup
        actionArea = `
            <div class="acceptance-box">
                <button class="btn-action btn-accept" onclick="acceptOrder(${job.id})">Accept Order</button>
                <button class="btn-action btn-reject" onclick="rejectOrder(${job.id})">Reject</button>
            </div>
            <div class="pickup-box" style="margin-top:10px;">
                <button class="btn-primary" onclick="verifyPickup(${order.id})">
                    <i class="fas fa-qrcode"></i> Scan/Verify Pickup
                </button>
            </div>`;
    } else if (['picked_up', 'out_for_delivery'].includes(job.status)) {
        // Step 2: Delivery with OTP
        actionArea = `
            <div class="otp-box">
                <input type="tel" id="delivery-otp" placeholder="Enter OTP" maxlength="6">
                <button onclick="completeOrder(${job.id})" class="btn-complete">Deliver</button>
            </div>`;
    }

    container.innerHTML = `
        <div class="job-card">
            <div class="job-header">
                <span>Order #${order.id}</span>
                <span class="amount">₹${order.final_amount}</span>
            </div>
            <div class="customer-info">
                <h4><i class="fas fa-user"></i> ${address.receiver_name || 'Customer'}</h4>
                <p><i class="fas fa-map-marker-alt"></i> ${address.full_address}</p>
                <div class="actions-row">
                    <a href="tel:${address.receiver_phone}" class="btn-small">Call</a>
                    <button class="btn-small" onclick="window.open('https://www.google.com/maps?q=${address.lat},${address.lng}')">Navigate</button>
                </div>
            </div>
            <div class="job-footer">${actionArea}</div>
        </div>`;
}

// Actions
window.acceptOrder = async (id) => {
    try {
        await ApiService.post(`/delivery/${id}/respond/`, { action: 'accept' });
        window.showToast("Order Accepted!", 'success');
        checkActiveJobs();
    } catch(e) { window.showToast(e.message, 'error'); }
};

window.verifyPickup = async (orderId) => {
    if(!confirm("Verify handover from warehouse?")) return;
    try {
        await ApiService.post('/delivery/verify-handover/', { order_id: orderId });
        window.showToast("Pickup Verified!", 'success');
        checkActiveJobs();
    } catch(e) { window.showToast(e.message, 'error'); }
};

window.completeOrder = async (id) => {
    const otp = document.getElementById('delivery-otp').value;
    if(otp.length !== 6) return window.showToast("Enter 6-digit OTP", 'error');
    
    try {
        await ApiService.post(`/delivery/${id}/complete/`, { otp });
        window.showToast("Order Delivered!", 'success');
        checkActiveJobs();
    } catch(e) { window.showToast(e.message, 'error'); }
};