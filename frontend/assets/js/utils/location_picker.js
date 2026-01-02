/* frontend/assets/js/utils/location_picker.js */

window.LocationPicker = {
    mode: 'SERVICE', 
    map: null,
    marker: null,
    geocoder: null,
    tempCoords: { lat: 12.9716, lng: 77.5946 },
    tempAddressData: null, 
    callback: null,

    /**
     * Entry point to open the map modal.
     * Use: open('SERVICE') OR open(callbackFunction)
     */
    async open(arg1 = 'SERVICE', arg2 = null) {
        // [FIX 2] Argument Handling: Agar function pass kiya hai toh usse callback set karo
        if (typeof arg1 === 'function') {
            this.mode = 'PICKER';
            this.callback = arg1;
        } else {
            this.mode = arg1;
            this.callback = arg2;
        }
        
        // 1. Inject UI
        this.injectModal();
        const modal = document.getElementById('loc-picker-modal');
        if(modal) modal.classList.add('active');

        // [UPDATED LOGIC] Manage Addresses button ab sabko dikhega (Guest ko bhi)
        // Lekin click karne par login maangega (niche injectModal mein logic hai)
        const manageBtn = document.getElementById('lp-manage-addrs');
        if (manageBtn) {
            manageBtn.style.display = 'block';
        }

        // 2. Determine Initial Center
        let storedCoords = null;
        try {
            const serviceCtx = JSON.parse(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.SERVICE_CONTEXT) || 'null');
            if (serviceCtx && serviceCtx.lat) {
                storedCoords = { lat: parseFloat(serviceCtx.lat), lng: parseFloat(serviceCtx.lng) };
            }
        } catch(e) {}

        if(storedCoords) this.tempCoords = storedCoords;

        // 3. Load Map Engine (Google Maps)
        try {
            if (window.MapsLoader) {
                setTimeout(async () => {
                    try {
                        await window.MapsLoader.load();
                        this.initMap();
                    } catch (innerErr) {
                        console.error("Maps load failed:", innerErr);
                        this.close();
                    }
                }, 0);
            }
        } catch (e) { this.close(); }
    },

    close() {
        const modal = document.getElementById('loc-picker-modal');
        if (modal) modal.classList.remove('active');
        this.tempAddressData = null;
        this.callback = null; // Callback reset karna zaroori hai
    },

    injectModal() {
        if (document.getElementById('loc-picker-modal')) return;

        const html = `
        <div id="loc-picker-modal" class="location-modal">
            <div class="modal-content-map">
                <div class="map-header">
                    <h4 id="lp-title">Select Location</h4>
                    <button onclick="window.LocationPicker.close()" class="close-btn">&times;</button>
                </div>
                
                <div class="map-container-wrapper" style="position: relative; flex: 1; width: 100%; height: 400px;">
                    <div id="lp-map" style="width: 100%; height: 100%;"></div>
                    <div class="center-pin-overlay" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -100%); z-index: 10; pointer-events: none;">
                         <i class="fas fa-map-marker-alt" style="font-size: 3rem; color: #ef4444; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));"></i>
                    </div>
                </div>
                
                <div class="loc-footer">
                    <div id="lp-address-text" class="text-muted small mb-2 text-truncate">Move map to adjust...</div>
                    <button id="lp-confirm-btn" class="btn btn-primary w-100" onclick="window.LocationPicker.confirmPin()">
                        Confirm Location
                    </button>
                    <button id="lp-manage-addrs" class="btn btn-link w-100 mt-2">Manage addresses</button>
                </div>
            </div>
        </div>
        
        <div id="address-details-modal" class="modal-overlay d-none">
            <div class="modal-box">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h3>Address Details</h3>
                    <button onclick="document.getElementById('address-details-modal').classList.add('d-none')" class="btn-close">&times;</button>
                </div>
                <form id="save-addr-form">
                    <input type="hidden" id="d-lat">
                    <input type="hidden" id="d-lng">
                    <div class="form-group mb-2">
                        <label class="small text-muted">House / Flat No *</label>
                        <input type="text" id="d-house" class="form-control" required placeholder="e.g. Flat 401">
                    </div>
                    <div class="form-group mb-2">
                        <label class="small text-muted">Apartment / Road Area *</label>
                        <input type="text" id="d-area" class="form-control" required>
                    </div>
                    <div class="form-group mb-2">
                        <label class="small text-muted">Landmark (Optional)</label>
                        <input type="text" id="d-landmark" class="form-control">
                    </div>
                    <div class="form-group mb-3">
                        <label class="small text-muted">Save As</label>
                        <div class="d-flex gap-2 mt-1">
                            <label class="chip-radio"><input type="radio" name="d-label" value="HOME" checked> <span>Home</span></label>
                            <label class="chip-radio"><input type="radio" name="d-label" value="WORK"> <span>Work</span></label>
                            <label class="chip-radio"><input type="radio" name="d-label" value="OTHER"> <span>Other</span></label>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Save Address</button>
                </form>
            </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', html);

        const form = document.getElementById('save-addr-form');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveAddressToDB();
            });
        }

        // [UPDATED] Manage Address Click Handler
        const manageBtn = document.getElementById('lp-manage-addrs');
        if (manageBtn) {
            manageBtn.onclick = () => {
                // Check if User is Logged In
                const token = localStorage.getItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token');
                
                if (token) {
                    // Logged In: Go to Addresses Page
                    window.location.href = 'addresses.html';
                } else {
                    // Guest: Show warning and redirect to Login
                    if (window.Toast) {
                        Toast.info("Please login to manage addresses");
                    } else {
                        alert("Please login first");
                    }
                    
                    setTimeout(() => {
                        window.location.href = window.APP_CONFIG?.ROUTES?.LOGIN || 'auth.html';
                    }, 500);
                }
            };
        }
    },

    initMap() {
        if (!this.map) {
            const mapEl = document.getElementById('lp-map');
            if(!mapEl) return;
            
            this.map = new google.maps.Map(mapEl, {
                center: this.tempCoords,
                zoom: 17,
                disableDefaultUI: true, 
                clickableIcons: false,
                gestureHandling: 'greedy' 
            });

            this.geocoder = new google.maps.Geocoder();

            this.map.addListener('idle', () => {
                const c = this.map.getCenter();
                this.tempCoords = { lat: c.lat(), lng: c.lng() };
                this.reverseGeocode(this.tempCoords.lat, this.tempCoords.lng);
            });
            
            this.reverseGeocode(this.tempCoords.lat, this.tempCoords.lng);

        } else {
            google.maps.event.trigger(this.map, 'resize');
            this.map.setCenter(this.tempCoords);
            this.map.setZoom(17);
        }
    },

    async reverseGeocode(lat, lng) {
        const btn = document.getElementById('lp-confirm-btn');
        const txt = document.getElementById('lp-address-text');
        
        if (btn) btn.disabled = true;
        if (txt) txt.innerText = "Fetching location...";
        
        if (!this.geocoder) return;

        try {
            const response = await this.geocoder.geocode({ location: { lat, lng } });
            
            if (response.results && response.results[0]) {
                const result = response.results[0];
                this.tempAddressData = result; 
                
                let display = result.formatted_address;
                if (txt) txt.innerText = display;
                if (btn) btn.disabled = false;
            } else {
                throw new Error("No results");
            }
        } catch (e) {
            console.warn("Geocode failed", e);
            if (txt) txt.innerText = "Unknown Location";
            if (btn) btn.disabled = false; 
        }
    },

    confirmPin() {
        const res = this.tempAddressData || {};
        
        // [FIX 2] Callback Support: Agar addresses.html ne function pass kiya hai, toh usse data bhejo
        if (this.callback) {
            let city = '';
            let pincode = '';
            if (res.address_components) {
                res.address_components.forEach(c => {
                    if (c.types.includes('locality')) city = c.long_name;
                    if (c.types.includes('postal_code')) pincode = c.long_name;
                });
            }

            this.callback({
                lat: this.tempCoords.lat,
                lng: this.tempCoords.lng,
                address: res.formatted_address || '',
                city: city || '',
                pincode: pincode || ''
            });
            this.close();
            return;
        }

        // Standard Service Mode (Browsing)
        if (this.mode === 'SERVICE') {
            let city = 'Unknown';
            let area = 'Pinned Location';

            if (res.address_components) {
                res.address_components.forEach(comp => {
                    if (comp.types.includes('locality')) city = comp.long_name;
                    if (comp.types.includes('sublocality') || comp.types.includes('neighborhood')) {
                        area = comp.long_name;
                    }
                });
            }

            if (window.LocationManager) {
                window.LocationManager.setServiceLocation({
                    lat: this.tempCoords.lat,
                    lng: this.tempCoords.lng,
                    city: city,
                    area_name: area,
                    formatted_address: res.formatted_address
                });
            }
            this.close();
            
        } else {
            // Standard Address Saving Mode (internal)
            this.close();
            const addrModal = document.getElementById('address-details-modal');
            if (addrModal) {
                addrModal.classList.remove('d-none');
                
                const latField = document.getElementById('d-lat');
                const lngField = document.getElementById('d-lng');
                if(latField) latField.value = this.tempCoords.lat;
                if(lngField) lngField.value = this.tempCoords.lng;

                const areaInput = document.getElementById('d-area');
                if (areaInput && res.formatted_address) {
                    areaInput.value = res.formatted_address; 
                }
            }
        }
    }, 

    async saveAddressToDB() {
        const payload = {
            latitude: document.getElementById('d-lat').value,
            longitude: document.getElementById('d-lng').value,
            google_address_text: document.getElementById('d-area').value,
            house_no: document.getElementById('d-house').value,
            apartment_name: document.getElementById('d-area').value,
            landmark: document.getElementById('d-landmark').value,
            label: document.querySelector('input[name="d-label"]:checked').value
        };

        try {
            await ApiService.post('/auth/customer/addresses/', payload);
            Toast.success("Address Saved Successfully");
            document.getElementById('address-details-modal').classList.add('d-none');
            
            if (this.callback) this.callback(); // Refresh logic if passed
            
        } catch (e) {
            console.error(e);
            let msg = "Failed to save address";
            if (e.responseJSON) msg = JSON.stringify(e.responseJSON);
            Toast.error(msg);
        }
    }
};