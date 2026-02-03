document.addEventListener('DOMContentLoaded', async () => {
    if (!localStorage.getItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = 'index.html';
        return;
    }
    await initDashboard();
    setInterval(checkActiveJobs, 10000); 
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
        console.error("Init Error:", e);
        if(e.message && e.message.includes('401')) logout();
    }
}

function updateStatusUI(isOnline) {
    const badge = document.getElementById('rider-status');
    if (isOnline) {
        badge.innerText = "Online";
        badge.className = "badge-online";
        document.body.classList.remove('is-offline');
    } else {
        badge.innerText = "Offline";
        badge.className = "badge-offline";
        document.body.classList.add('is-offline');
    }
}

window.toggleOnline = async function(el) {
    const isOnline = el.checked;
    try {
        await ApiService.post('/riders/availability/', { is_available: isOnline });
        updateStatusUI(isOnline);
        if(isOnline) checkActiveJobs();
    } catch (e) {
        el.checked = !isOnline;
        alert("Failed to update status. Check connection.");
    }
};

async function checkActiveJobs() {
    if (!document.getElementById('online-toggle').checked) return;

    try {
        const deliveries = await ApiService.get('/delivery/me/');
        
        const activeJob = deliveries.find(d => ['assigned', 'picked_up', 'out_for_delivery'].includes(d.status));
        const container = document.getElementById('active-job-area');
        
        if (activeJob) {
            renderJobCard(activeJob, container);
        } else {
            container.innerHTML = `
                <div class="no-job">
                    <i class="fas fa-motorcycle"></i>
                    <p>Scanning for orders...</p>
                    <div class="pulse-ring"></div>
                </div>`;
        }
    } catch (e) { console.error("Job fetch failed", e); }
}

function renderJobCard(job, container) {
    const order = job.order;
    const address = order.delivery_address_json || {};
    const lat = address.lat || 0;
    const lng = address.lng || 0;
    
    const mapLink = `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
    const receiverName = address.receiver_name || "Customer";
    const fullAddr = address.full_address || "Address details unavailable";
    const phone = address.receiver_phone || "";

    let actionBtn = '';
    let statusBadge = '';

    if (job.status === 'assigned') {
        statusBadge = '<span class="status-tag tag-new">New Assignment</span>';
        actionBtn = `<button class="btn-action btn-pickup" onclick="scanQR(${order.id})">
                        <i class="fas fa-box"></i> Picked Up from Warehouse
                     </button>`;
    } else if (['picked_up', 'out_for_delivery'].includes(job.status)) {
        statusBadge = '<span class="status-tag tag-progress">Out for Delivery</span>';
        actionBtn = `
            <div class="otp-box">
                <label>Ask Customer for OTP:</label>
                <div class="otp-input-group">
                    <input type="tel" id="delivery-otp" placeholder="Enter 6-digit OTP" maxlength="6">
                    <button onclick="completeOrder(${job.id})" class="btn-action btn-complete">
                        <i class="fas fa-check-circle"></i> Complete
                    </button>
                </div>
            </div>`;
    }

    container.innerHTML = `
        <div class="job-card">
            <div class="job-header">
                <div>
                    <span class="order-id">Order #${order.id}</span>
                    ${statusBadge}
                </div>
                <span class="amount">₹${order.final_amount}</span>
            </div>
            <div class="customer-info">
                <h4>${receiverName}</h4>
                <p><i class="fas fa-map-marker-alt"></i> ${fullAddr}</p>
                <div class="actions-row">
                    <a href="tel:${phone}" class="btn-small"><i class="fas fa-phone"></i> Call</a>
                    <a href="${mapLink}" target="_blank" class="btn-small"><i class="fas fa-location-arrow"></i> Navigate</a>
                </div>
            </div>
            <div class="job-items">
                <small>${order.items ? order.items.length : 0} Items in package</small>
            </div>
            <div class="job-footer">
                ${actionBtn}
            </div>
        </div>
    `;
}

window.completeOrder = async function(id) {
    const otpInput = document.getElementById('delivery-otp');
    const otp = otpInput.value;
    
    if(!otp || otp.length !== 6) {
        alert("Please enter the valid 6-digit OTP provided by the customer.");
        return;
    }
    
    const btn = document.querySelector('.btn-complete');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verifying...';
    btn.disabled = true;

    try {
        await ApiService.post(`/delivery/${id}/complete/`, { otp });
        alert("✅ Order Delivered Successfully!");
        await checkActiveJobs();
        window.location.reload();
    } catch(e) {
        console.error(e);
        let msg = "Failed to complete delivery.";
        if(e.message) msg = e.message;
        if(e.error && e.error.detail) msg = e.error.detail;
        
        alert("❌ Error: " + msg);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
};

window.scanQR = async function(orderId) {
    const confirmPickup = confirm(`Simulate Scanning QR Code for Order #${orderId}?\n\n(In production, this opens camera)`);
    if(!confirmPickup) return;

    try {
        await ApiService.post('/delivery/verify-handover/', { order_id: orderId });
        
        alert("✅ Pickup Verified! Status Updated.");
        checkActiveJobs(); 
    } catch (e) {
        alert("❌ Handover Failed: " + (e.message || "Unknown error"));
    }
};

window.logout = function() {
    if(confirm("Are you sure you want to logout?")) {
        localStorage.clear();
        window.location.href = 'index.html';
    }
};
