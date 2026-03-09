// frontend/assets/js/pages/rider.js

document.addEventListener('DOMContentLoaded', initRiderApp);

async function initRiderApp() {
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = 'login.html';
        return;
    }

    try {
        await loadProfile();
        await loadActiveJob();
        // Poll for new jobs every 15 seconds if online
        setInterval(loadActiveJob, 15000);
    } catch (e) {
        console.error(e);
        if(e.status === 403) {
            alert("Rider Profile not found. Please contact admin.");
            logout();
        }
    }
}

// 1. Profile & Status
async function loadProfile() {
    const profile = await ApiService.get('/riders/me/');
    
    // UI Update
    const toggle = document.getElementById('online-toggle');
    const statusText = document.getElementById('status-text');
    const content = document.getElementById('dashboard-content');

    if (profile.is_available) {
        toggle.checked = true;
        statusText.innerText = "Online";
        statusText.className = "text-success m-0 ml-2";
        content.classList.remove('offline-overlay');
    } else {
        toggle.checked = false;
        statusText.innerText = "Offline";
        statusText.className = "text-muted m-0 ml-2";
        content.classList.add('offline-overlay');
    }
}

// 2. Toggle Online/Offline
window.toggleStatus = async function(el) {
    const isOnline = el.checked;
    const statusText = document.getElementById('status-text');
    const content = document.getElementById('dashboard-content');

    try {
        await ApiService.post('/riders/availability/', { is_available: isOnline });
        
        if (isOnline) {
            statusText.innerText = "Online";
            statusText.className = "text-success m-0 ml-2";
            content.classList.remove('offline-overlay');
            loadActiveJob(); // Check immediately
        } else {
            statusText.innerText = "Offline";
            statusText.className = "text-muted m-0 ml-2";
            content.classList.add('offline-overlay');
        }
    } catch (e) {
        el.checked = !isOnline; // Revert UI on failure
        alert(e.message || "Failed to update status");
    }
}

// 3. Load Active Delivery
async function loadActiveJob() {
    const container = document.getElementById('active-order-container');
    
    // Only fetch if online (optimization)
    if (document.getElementById('online-toggle').checked === false) return;

    try {
        const res = await ApiService.get('/delivery/me/');
        // Filter tasks that are NOT delivered/failed
        const activeJob = res.find(d => ['assigned', 'picked_up', 'out_for_delivery'].includes(d.status));

        if (activeJob) {
            renderActiveJob(activeJob, container);
        } else {
            container.innerHTML = `
                <div class="text-center py-5">
                    <img src="https://cdn-icons-png.flaticon.com/512/2769/2769339.png" width="80" style="opacity:0.5">
                    <h5 class="mt-3 text-muted">No Active Orders</h5>
                    <p class="small text-muted">Keep the app open. Orders are auto-assigned.</p>
                </div>
            `;
        }
    } catch (e) {
        console.error("Job Fetch Error", e);
    }
}

function renderActiveJob(job, container) {
    const order = job.order;
    const address = order.delivery_address_json;
    
    // Google Maps Link
    const mapUrl = `https://www.google.com/maps/dir/?api=1&destination=${address.lat},${address.lng}`;

    let actionBtn = '';
    
    if (job.status === 'assigned') {
        actionBtn = `
            <div class="alert alert-info small">Go to Warehouse to pick up order.</div>
            <button onclick="markPickedUp(${job.id})" class="btn btn-warning w-100">
                Pick Up Order (Scan)
            </button>
        `;
        // Note: Real flow uses QR Scan, for simple version we auto-verify or add a simple button
        // For 'simple app', let's assume they pick up and status changes manually via Warehouse App 
        // OR we give a button here if Warehouse App is not strict.
        // Based on your requirement "simple", let's assume Order is ALREADY "out_for_delivery" or we simplify flow.
        // Actually, backend expects 'out_for_delivery' status for delivery.
        // Let's simplified: If status is 'assigned', show warehouse address.
    } 
    
    if (job.status === 'out_for_delivery' || job.status === 'picked_up') {
        actionBtn = `
            <div class="form-group mb-2">
                <input type="number" id="otp-input" class="form-control text-center" placeholder="Enter Customer OTP (6 digits)" style="font-size:1.2rem; letter-spacing:5px;">
            </div>
            <button onclick="completeDelivery(${job.id})" class="btn btn-success w-100 py-3 shadow">
                Complete Delivery <i class="fas fa-check-circle"></i>
            </button>
        `;
    }

    container.innerHTML = `
        <div class="order-card">
            <div class="d-flex justify-between mb-2">
                <span class="badge badge-primary">Order #${order.id}</span>
                <span class="font-bold text-success">${Formatters.currency(order.final_amount)}</span>
            </div>
            
            <h5 class="mb-1">${address.receiver_name || 'Customer'}</h5>
            <p class="text-muted small mb-3">
                <i class="fas fa-map-marker-alt text-danger"></i> ${address.full_address}
            </p>

            <div class="d-grid gap-2 mb-3" style="grid-template-columns: 1fr 1fr;">
                <a href="tel:${address.receiver_phone}" class="btn btn-outline btn-sm">
                    <i class="fas fa-phone"></i> Call
                </a>
                <a href="${mapUrl}" target="_blank" class="btn btn-outline btn-sm">
                    <i class="fas fa-directions"></i> Map
                </a>
            </div>

            <hr class="my-3">
            
            ${actionBtn}
        </div>
    `;
}

// 4. Actions
window.completeDelivery = async function(deliveryId) {
    const otp = document.getElementById('otp-input').value;
    if (!otp || otp.length !== 6) {
        if(window.Toast) Toast.error("Please ask customer for 6-digit OTP");
        else alert("Enter valid OTP");
        return;
    }

    try {
        await ApiService.post(`/delivery/${deliveryId}/complete/`, { otp: otp });
        if(window.Toast) Toast.success("Delivery Completed! Great Job.");
        else alert("Delivery Success!");
        
        loadActiveJob(); // Refresh
        // Update Earnings (optional fetch)
    } catch (e) {
        if(window.Toast) Toast.error(e.message || "OTP Invalid");
        else alert(e.message || "Failed");
    }
};

window.logout = function() {
    localStorage.clear();
    window.location.href = 'login.html';
};