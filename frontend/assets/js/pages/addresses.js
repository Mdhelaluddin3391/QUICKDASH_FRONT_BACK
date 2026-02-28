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
window.openAddressModal = function() {
    // Step 1: Open Location Picker
    if (window.LocationPicker) {
        window.LocationPicker.open('PICKER', (locationData) => {
            // Step 2: Callback when user confirms pin
            openAddressForm(locationData);
        });
    } else {
        if(window.Toast) Toast.error("Map module loading... please try again.");
    }
};

// --- FIX APPLIED HERE: Form open logic updated to clear old map address ---
// --- UPDATED: Form open logic to auto-fill map data ---
function openAddressForm(data) {
    const modal = document.getElementById('address-modal');
    if(modal) modal.classList.add('active');

    // Auto-Fill Lat/Lng (Hidden fields)
    document.getElementById('a-lat').value = data.lat || '';
    document.getElementById('a-lng').value = data.lng || '';
    document.getElementById('a-google-text').value = data.address || '';
    
    // Display the actual Map Address that the user pinned
    const displaySpan = document.getElementById('display-map-address');
    if(displaySpan) {
        displaySpan.innerText = data.address || "Pin Location Selected (Fill missing details below)";
        displaySpan.style.color = "#2c3e50"; 
    }

    // ✅ AUTO FILL FROM MAP PIN
    // Yahan hum map se aayi details ko pre-fill kar rahe hain
    document.getElementById('a-city').value = data.city || ''; 
    
    const pinEl = document.getElementById('a-pin');
    if(pinEl) pinEl.value = data.pincode || ''; 
    
    // Building/Street/Area details auto-fill
    document.getElementById('a-building').value = data.building || ''; 
    document.getElementById('a-landmark').value = data.area || ''; 
    document.getElementById('a-house').value = data.houseNo || '';
    document.getElementById('a-floor').value = ''; // Floor hamesha blank rahega

    // ✅ AUTO FILL NAME & PHONE (Agar localStorage mein user login details hain)
    try {
        const userStr = localStorage.getItem('user'); // Ya jo bhi aapki storage key ho: APP_CONFIG.STORAGE_KEYS.USER
        if (userStr) {
            const user = JSON.parse(userStr);
            const nameEl = document.getElementById('a-name');
            const phoneEl = document.getElementById('a-phone');
            
            // Agar input khali hai, tabhi user ki details fill karo
            if(nameEl && !nameEl.value) {
                nameEl.value = user.full_name || user.first_name || user.name || '';
            }
            if(phoneEl && !phoneEl.value) {
                phoneEl.value = user.phone_number || user.phone || '';
            }
        }
    } catch (e) {
        console.warn("Could not auto-fill user details", e);
    }
}

// Close Modal Function
window.closeModal = function() {
    const modal = document.getElementById('address-modal');
    if(modal) modal.classList.remove('active');
}

// --- 3. Form Submission ---
// --- 3. Form Submission ---
async function saveAddress(e) {
    e.preventDefault();

    // 1. Sabse pehle saari values get kar rahe hain (.trim() laga kar space hata rahe hain)
    const name = document.getElementById('a-name').value.trim();
    const phone = document.getElementById('a-phone').value.trim();
    const house = document.getElementById('a-house').value.trim();
    const building = document.getElementById('a-building').value.trim();
    const landmark = document.getElementById('a-landmark').value.trim();
    const city = document.getElementById('a-city').value.trim();
    const pincode = document.getElementById('a-pin').value.trim();
    const lat = document.getElementById('a-lat').value;
    const lng = document.getElementById('a-lng').value;
    const floor = document.getElementById('a-floor').value.trim();

    // 2. 🔴 MANUAL STRICT VALIDATION (Yeh line API call ko rok degi agar details khali hain)
    if (!name || !phone || !house || !building || !city || !pincode || !landmark) {
        if(window.Toast) Toast.error("Please fill all required fields, including Landmark.");
        else alert("Please fill all required fields, including Landmark!");
        return; // Function yahin se waapis chala jayega, aage execute nahi hoga
    }

    if (phone.length < 10) {
        if(window.Toast) Toast.error("Please enter a valid 10-digit phone number");
        else alert("Please enter a valid 10-digit phone number");
        return;
    }

    // 3. Sab theek hai toh Button ko loading state me daalo
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Saving...";

    // 4. Serviceability Check (Updated with Toast)
    try {
        const checkRes = await ApiService.post('/warehouse/find-serviceable/', { latitude: lat, longitude: lng });
        if (!checkRes.serviceable) {
            // Browser alert ki jagah ab Toast show hoga
            if(window.Toast) {
                // Agar aapke Toast me warning color hai toh wo, warna normal error red color me show karega
                if(typeof Toast.warning === 'function') Toast.warning("Location unserviceable, but address will be saved.");
                else Toast.error("Location unserviceable, but address will be saved.");
            }
        }
    } catch (checkError) {
        console.warn("Serviceability check failed, proceeding with save", checkError);
    }

    // 5. Address combine karne ka Logic
    let fullAddressText = `${house}, ${building}`;
    if (landmark) fullAddressText += `, ${landmark}`;
    fullAddressText += `, ${city}, ${pincode}`;

    // 6. Payload Setup
    const payload = {
        label: document.querySelector('input[name="atype"]:checked').value,
        house_no: house,
        apartment_name: building,
        landmark: landmark,
        google_address_text: fullAddressText,
        city: city,
        pincode: pincode,
        latitude: lat,
        longitude: lng,
        receiver_name: name,
        receiver_phone: phone,
        floor_no: floor,
        is_default: false 
    };

    // 7. API Call
    try {
        await ApiService.post('/auth/customer/addresses/', payload);
        
        // Success
        ApiService.clearCache();
        closeModal();
        loadAddresses(); // Reload list
        if(window.Toast) Toast.success("Address saved successfully");
        
    } catch (err) {
        console.error(err);
        if(window.Toast) Toast.error(err.message || "Failed to save address");
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

// --- 🌟 CUSTOM CONFIRMATION POPUP LOGIC ---
window.customConfirm = function(message, callback) {
    // Agar pehle se koi popup hai toh hata do
    const existingOverlay = document.getElementById('custom-confirm-overlay');
    if (existingOverlay) existingOverlay.remove();

    // Naya overlay aur box create karo
    const overlay = document.createElement('div');
    overlay.id = 'custom-confirm-overlay';
    overlay.className = 'modal-overlay active';
    overlay.style.zIndex = '99999'; // Sabse upar dikhane ke liye
    overlay.style.display = 'flex';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';

    const box = document.createElement('div');
    box.className = 'modal-box';
    box.style.maxWidth = '350px';
    box.style.textAlign = 'center';
    box.style.padding = '30px 20px';
    box.style.borderRadius = '12px';
    box.style.transform = 'scale(0.9)';
    box.style.animation = 'popIn 0.3s forwards ease-out'; // Chhoti si animation

    // Animation ke liye CSS (dynamically add)
    if (!document.getElementById('confirm-styles')) {
        const style = document.createElement('style');
        style.id = 'confirm-styles';
        style.innerHTML = `@keyframes popIn { to { transform: scale(1); } }`;
        document.head.appendChild(style);
    }

    // Modal ka design (Red warning icon aur buttons)
    box.innerHTML = `
        <div style="font-size: 3.5rem; color: #ef4444; margin-bottom: 15px;">
            <i class="fas fa-exclamation-circle"></i>
        </div>
        <h4 style="margin-bottom: 10px; color: #2c3e50; font-size:1.2rem;">Are you sure?</h4>
        <p style="color: #64748b; margin-bottom: 25px; font-size:0.95rem;">${message}</p>
        <div style="display: flex; gap: 12px; justify-content: center;">
            <button id="confirm-cancel-btn" class="btn btn-outline" style="flex: 1; border-radius: 8px;">Cancel</button>
            <button id="confirm-ok-btn" class="btn btn-primary" style="flex: 1; background-color: #ef4444; border-color: #ef4444; border-radius: 8px;">Delete</button>
        </div>
    `;

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    // Button Clicks Handle karna
    document.getElementById('confirm-cancel-btn').onclick = () => {
        overlay.remove();
    };
    
    document.getElementById('confirm-ok-btn').onclick = () => {
        overlay.remove();
        if(callback) callback(); // Delete API call run karega
    };
};

// --- UPDATED DELETE FUNCTION ---
window.deleteAddress = function(id) {
    // Browser ke confirm ki jagah apna custom modal call karo
    customConfirm("Do you really want to delete this address? This action cannot be undone.", async () => {
        try {
            await ApiService.delete(`/auth/customer/addresses/${id}/`);
            if(window.Toast) Toast.success("Address deleted successfully");
            ApiService.clearCache();
            loadAddresses(); // List wapas reload karega
        } catch (e) {
            console.error(e);
            if(window.Toast) Toast.error("Failed to delete address");
        }
    });
};

function setupModalHandlers() {
    const form = document.getElementById('address-form');
    if (form) form.addEventListener('submit', saveAddress);
}