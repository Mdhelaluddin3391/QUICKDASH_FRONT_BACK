document.addEventListener('DOMContentLoaded', () => {
    // Auth Check
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = '/auth.html';
        return;
    }

    loadAddresses();
    setupModalHandlers();
});

// --- 1. Load & Render Addresses ---
async function loadAddresses() {
    // FIX: HTML mein ID 'addr-grid' hai
    const container = document.getElementById('addr-grid'); 
    if (!container) return; 

    container.innerHTML = '<div class="loader-spinner"></div>';

    try {
        const res = await ApiService.get('/auth/customer/addresses/');
        const addresses = Array.isArray(res) ? res : res.results;

        if (addresses.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; text-align:center; padding: 40px;">
                    <i class="fas fa-map-marked-alt" style="font-size:3rem; color:#eee; margin-bottom:15px;"></i>
                    <p class="text-muted">No addresses saved yet.</p>
                    <button class="btn btn-primary" onclick="openAddressModal()">Add New Address</button>
                </div>`;
            return;
        }

        container.innerHTML = addresses.map(addr => `
            <div class="address-card">
                <div class="card-header">
                    <span class="badge badge-${addr.label.toLowerCase()}">${addr.label}</span>
                    ${addr.is_default ? '<span class="text-success small"><i class="fas fa-check"></i> Default</span>' : ''}
                </div>
                <div class="card-body">
                    <p class="mb-1"><strong>${addr.house_no || ''} ${addr.apartment_name || ''}</strong></p>
                    <p class="text-muted small">${addr.google_address_text || addr.address_line || 'No details'}</p>
                    <p class="text-muted small">${addr.city} - ${addr.pincode}</p>
                </div>
                <div class="card-actions">
                    <button class="btn-sm btn-outline-danger" onclick="deleteAddress('${addr.id}')">Delete</button>
                </div>
            </div>
        `).join('') + `
            <div class="address-card add-new-card" onclick="openAddressModal()">
                <div class="dashed-border">
                    <i class="fas fa-plus-circle"></i>
                    <span>Add New Address</span>
                </div>
            </div>
        `;

    } catch (e) {
        console.error(e);
        container.innerHTML = '<p class="text-danger">Failed to load addresses.</p>';
    }
}

// --- 2. Add Address Flow (Map First) ---
// FIX: Function rename kiya taaki HTML ke 'onclick' se match kare
window.openAddressModal = function() {
    // Step 1: Open Location Picker
    if (window.LocationPicker) {
        window.LocationPicker.open('PICKER', (locationData) => {
            // Step 2: Callback when user confirms pin
            openAddressForm(locationData);
        });
    } else {
        alert("Map module loading... please try again.");
    }
};

function openAddressForm(data) {
    // FIX: HTML mein ID 'address-modal' hai
    const modal = document.getElementById('address-modal');
    if(modal) modal.classList.add('active');

    // Auto-Fill Form
    document.getElementById('a-lat').value = data.lat;
    document.getElementById('a-lng').value = data.lng;
    
    // FIX: Address display ke liye span tag update
    const displaySpan = document.getElementById('display-map-address');
    if(displaySpan) displaySpan.innerText = data.address || 'Selected Location';
    
    document.getElementById('a-google-text').value = data.address || '';
    document.getElementById('a-city').value = data.city || '';
    
    // FIX: HTML mein ID 'a-pin' hai ('a-pincode' nahi)
    const pinEl = document.getElementById('a-pin');
    if(pinEl) pinEl.value = data.pincode || ''; 
    
    // Reset other fields
    document.getElementById('a-house').value = '';
    document.getElementById('a-building').value = '';
    document.getElementById('a-landmark').value = '';
}

// FIX: Close Modal Function (HTML mein onclick="closeModal()" hai)
window.closeModal = function() {
    const modal = document.getElementById('address-modal');
    if(modal) modal.classList.remove('active');
}

// --- 3. Form Submission ---
async function saveAddress(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Saving...";

    const lat = document.getElementById('a-lat').value;
    const lng = document.getElementById('a-lng').value;

    // Serviceability Check
    try {
        const checkRes = await ApiService.post('/warehouse/find-serviceable/', { latitude: lat, longitude: lng });
        if (!checkRes.serviceable) {
            // Show warning but continue
            alert("Location currently unserviceable, but address will be saved.");
        }
    } catch (checkError) {
        console.warn("Serviceability check failed, proceeding with save", checkError);
    }

    const payload = {
        label: document.querySelector('input[name="atype"]:checked').value,
        house_no: document.getElementById('a-house').value,
        apartment_name: document.getElementById('a-building').value,
        landmark: document.getElementById('a-landmark').value,
        google_address_text: document.getElementById('a-google-text').value,
        city: document.getElementById('a-city').value,
        pincode: document.getElementById('a-pin').value, // FIX: Correct ID
        latitude: lat,
        longitude: lng,
        receiver_name: document.getElementById('a-name').value,
        receiver_phone: document.getElementById('a-phone').value,
        floor_no: document.getElementById('a-floor').value,
        is_default: false 
    };

    try {
        await ApiService.post('/auth/customer/addresses/', payload);
        
        // Success
        closeModal();
        loadAddresses(); // Reload list
        if(window.Toast) Toast.success("Address saved successfully");
        
    } catch (err) {
        console.error(err);
        alert(err.message || "Failed to save address");
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

window.deleteAddress = async function(id) {
    if (!confirm("Are you sure you want to delete this address?")) return;
    try {
        await ApiService.delete(`/auth/customer/addresses/${id}/`);
        if(window.Toast) Toast.success("Address deleted");
        loadAddresses();
    } catch (e) {
        alert("Failed to delete address");
    }
}

function setupModalHandlers() {
    // FIX: HTML mein Form ID 'address-form' hai
    const form = document.getElementById('address-form');
    if (form) form.addEventListener('submit', saveAddress);
}