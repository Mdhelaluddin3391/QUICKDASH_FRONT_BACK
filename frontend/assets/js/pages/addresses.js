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
        alert("Map module loading... please try again.");
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

    // 4. Serviceability Check (Purana Logic as it is)
    try {
        const checkRes = await ApiService.post('/warehouse/find-serviceable/', { latitude: lat, longitude: lng });
        if (!checkRes.serviceable) {
            alert("Location currently unserviceable, but address will be saved.");
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
            ApiService.clearCache();
        loadAddresses();
    } catch (e) {
        alert("Failed to delete address");
    }
}

function setupModalHandlers() {
    const form = document.getElementById('address-form');
    if (form) form.addEventListener('submit', saveAddress);
}