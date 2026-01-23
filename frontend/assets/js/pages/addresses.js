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
    const container = document.getElementById('address-grid');
    if (!container) return; // May be on a different page

    container.innerHTML = '<div class="loader-spinner"></div>';

    try {
        const res = await ApiService.get('/auth/customer/addresses/');
        const addresses = Array.isArray(res) ? res : res.results;

        if (addresses.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-map-marked-alt"></i>
                    <p>No addresses saved yet.</p>
                    <button class="btn btn-primary" onclick="openAddAddressFlow()">Add New Address</button>
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
                    <p class="text-muted small">${addr.address_line}</p>
                    <p class="text-muted small">${addr.city} - ${addr.pincode}</p>
                </div>
                <div class="card-actions">
                    <button class="btn-sm btn-outline-danger" onclick="deleteAddress('${addr.id}')">Delete</button>
                </div>
            </div>
        `).join('') + `
            <div class="address-card add-new-card" onclick="openAddAddressFlow()">
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
window.openAddAddressFlow = function() {
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
    // Show the form modal
    const modal = document.getElementById('address-form-modal');
    modal.classList.add('active');

    // Auto-Fill Form
    document.getElementById('a-lat').value = data.lat;
    document.getElementById('a-lng').value = data.lng;
    document.getElementById('a-google-text').value = data.address || '';
    document.getElementById('a-city').value = data.city || '';
    document.getElementById('a-pincode').value = data.pincode || '';
    
    // Reset other fields
    document.getElementById('a-house').value = '';
    document.getElementById('a-landmark').value = '';
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
        pincode: document.getElementById('a-pincode').value,
        latitude: lat,
        longitude: lng,
        receiver_name: document.getElementById('a-name').value,
        receiver_phone: document.getElementById('a-phone').value,
        floor_no: document.getElementById('a-floor').value,
        is_default: false // or from a checkbox if added
    };

    try {
        await ApiService.post('/auth/customer/addresses/', payload);
        
        // Success
        document.getElementById('address-form-modal').classList.remove('active');
        loadAddresses(); // Reload list
        
        // If this was the first address, sync location context
        if (payload.is_default) {
            // Optional: Auto-select this location
            // window.LocationManager.setDeliveryAddress(...) 
        }
    } catch (err) {
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
        loadAddresses();
    } catch (e) {
        alert("Failed to delete address");
    }
}

function setupModalHandlers() {
    const form = document.getElementById('new-address-form');
    if (form) form.addEventListener('submit', saveAddress);

    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.onclick = () => {
            document.getElementById('address-form-modal').classList.remove('active');
        };
    });
}