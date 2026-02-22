let locationWatchId = null;

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
        startLocationTracking(); // 🔥 Start Tracking
    } else {
        badge.innerText = "Offline";
        badge.className = "badge-offline";
        document.body.classList.add('is-offline');
        stopLocationTracking();  // 🔥 Stop Tracking
    }
}

window.toggleOnline = async function(el) {
    const isOnline = el.checked;
    try {
        await ApiService.post('/riders/availability/', { is_available: isOnline });
        updateStatusUI(isOnline);
        if(isOnline) {
            checkActiveJobs();
            window.showToast("You are now Online", 'success');
        } else {
            window.showToast("You are Offline", 'info');
        }
    } catch (e) {
        el.checked = !isOnline;
        window.showToast("Failed to update status. Check connection.", 'error');
    }
};

// ==========================================
// 📍 SOLID LOCATION TRACKING SYSTEM
// ==========================================
function startLocationTracking() {
    if (!navigator.geolocation) {
        window.showToast("Geolocation is not supported by your browser", 'error');
        return;
    }

    // Clear any existing watch
    if (locationWatchId !== null) stopLocationTracking();

    locationWatchId = navigator.geolocation.watchPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            try {
                // Send coordinates to backend periodically
                await ApiService.post('/riders/location/', { lat, lng });
                console.log(`📍 Location updated: ${lat}, ${lng}`);
            } catch(e) {
                console.warn("Could not sync location to server", e);
            }
        },
        (error) => {
            console.error("GPS Error:", error);
            window.showToast("Please enable GPS/Location access", 'error');
        },
        {
            enableHighAccuracy: true,  // Important for real-time tracking
            maximumAge: 5000,          // Accept max 5-second old cached location
            timeout: 10000             // Timeout after 10 seconds
        }
    );
}

function stopLocationTracking() {
    if (locationWatchId !== null) {
        navigator.geolocation.clearWatch(locationWatchId);
        locationWatchId = null;
        console.log("📍 Tracking stopped.");
    }
}
// ==========================================


async function checkActiveJobs() {
    if (!document.getElementById('online-toggle').checked) return;

    try {
        const deliveries = await ApiService.get('/delivery/me/');
        // Find first active job (prioritize: pending acceptance > picked up > out for delivery)
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
    
    const mapLink = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
    const receiverName = address.receiver_name || "Customer";
    const fullAddr = address.full_address || "Address details unavailable";
    const phone = address.receiver_phone || "";
    
    // 🔥 Item List Build Karna
    const itemsListHTML = order.items && order.items.length > 0 
        ? `<ul class="order-items-list" style="margin: 10px 0; padding-left: 20px; font-size: 13px;">
            ${order.items.map(i => `<li>${i.quantity}x ${i.product_name}</li>`).join('')}
           </ul>`
        : `<p style="font-size: 13px; color: #888;">Items details not available</p>`;

    let actionBtn = '';
    let statusBadge = '';

    if (job.status === 'assigned') {
        statusBadge = '<span class="status-tag tag-new">🆕 New Order - Action Required</span>';
        actionBtn = `
            <div class="acceptance-box" style="display: flex; gap: 10px; margin-bottom: 15px;">
                <button class="btn-action btn-accept" onclick="acceptOrder(${job.id})" style="flex: 1; background: #10b981;">
                    <i class="fas fa-check"></i> Accept Order
                </button>
                <button class="btn-action btn-reject" onclick="rejectOrder(${job.id})" style="flex: 1; background: #ef4444;">
                    <i class="fas fa-times"></i> Reject
                </button>
            </div>
            <div style="text-align: center; font-size: 12px; color: #666; margin-bottom: 15px;">
                After accepting, you'll pick up from the warehouse
            </div>`;
    } else if (['picked_up', 'out_for_delivery'].includes(job.status)) {
        statusBadge = '<span class="status-tag tag-progress">🚚 Out for Delivery</span>';
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
        <div class="job-card" style="text-align: left;">
            <div class="job-header">
                <div>
                    <span class="order-id">Order #${order.id}</span>
                    ${statusBadge}
                </div>
                <div style="text-align: right;">
                    <span class="amount">₹${order.final_amount}</span><br>
                    <small style="color:${order.payment_method === 'COD' ? '#eab308' : '#10b981'}">
                        ${order.payment_method === 'COD' ? 'Collect Cash' : 'Paid Online'}
                    </small>
                </div>
            </div>
            
            <div class="customer-info">
                <h4><i class="fas fa-user"></i> ${receiverName}</h4>
                <p><i class="fas fa-map-marker-alt"></i> ${fullAddr}</p>
                <div class="actions-row">
                    <a href="tel:${phone}" class="btn-small"><i class="fas fa-phone"></i> Call</a>
                    <a href="${mapLink}" target="_blank" class="btn-small btn-map"><i class="fas fa-location-arrow"></i> Navigate</a>
                </div>
            </div>

            <div class="job-items" style="background: #f8fafc; padding: 10px; border-radius: 6px; margin-bottom: 15px;">
                <strong><i class="fas fa-shopping-bag"></i> Package Contents:</strong>
                ${itemsListHTML}
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
        window.showToast("Please enter the valid 6-digit OTP", 'error');
        return;
    }
    
    const btn = document.querySelector('.btn-complete');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verifying...';
    btn.disabled = true;

    try {
        await ApiService.post(`/delivery/${id}/complete/`, { otp });
        window.showToast("✅ Order Delivered Successfully!", 'success');
        await checkActiveJobs();
    } catch(e) {
        console.error(e);
        let msg = "Failed to complete delivery.";
        if(e.message) msg = e.message;
        if(e.error && e.error.detail) msg = e.error.detail;
        
        window.showToast("❌ Error: " + msg, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
};

// ==========================================
// 🎯 Accept/Reject New Orders
// ==========================================
window.acceptOrder = async function(deliveryId) {
    const btn = document.querySelector('.btn-accept');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Accepting...';
    btn.disabled = true;

    try {
        await ApiService.post(`/delivery/${deliveryId}/respond/`, { action: 'accept' });
        window.showToast("✅ Order Accepted! Go to warehouse to pick up.", 'success');
        await checkActiveJobs();
    } catch (e) {
        console.error("Accept Error:", e);
        let msg = e.message || "Failed to accept order";
        window.showToast("❌ Error: " + msg, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
};

window.rejectOrder = async function(deliveryId) {
    const confirmed = confirm("Are you sure you want to reject this order?");
    if (!confirmed) return;

    const btn = document.querySelector('.btn-reject');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Rejecting...';
    btn.disabled = true;

    try {
        await ApiService.post(`/delivery/${deliveryId}/respond/`, { action: 'reject' });
        window.showToast("✅ Order Rejected. Looking for next delivery...", 'info');
        await checkActiveJobs();
    } catch (e) {
        console.error("Reject Error:", e);
        let msg = e.message || "Failed to reject order";
        window.showToast("❌ Error: " + msg, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
};
// ==========================================


window.scanQR = async function(orderId) {
    const confirmPickup = confirm(`Simulate Scanning QR Code for Order #${orderId}?\n\n(In production, this opens camera)`);
    if(!confirmPickup) return;

    try {
        await ApiService.post('/delivery/verify-handover/', { order_id: orderId });
        
        window.showToast("✅ Pickup Verified! Status Updated.", 'success');
        checkActiveJobs(); 
    } catch (e) {
        window.showToast("❌ Handover Failed: " + (e.message || "Unknown error"), 'error');
    }
};

window.logout = function() {
    if(confirm("Are you sure you want to logout?")) {
        stopLocationTracking();
        localStorage.clear();
        window.location.href = 'index.html';
    }
};