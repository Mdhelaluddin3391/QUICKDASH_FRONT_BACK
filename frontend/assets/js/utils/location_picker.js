/* frontend/assets/js/utils/location_picker.js */

window.LocationPicker = {
    mode: 'SERVICE', // 'SERVICE' (Browsing) or 'PICKER' (Address Form Callback)
    
    // Map Instances
    googleMap: null,
    leafletMap: null,
    geocoder: null, // Google Geocoder instance
    
    // State
    tempCoords: { lat: 12.9716, lng: 77.5946 }, // Default: Bengaluru
    tempAddressData: null, 
    callback: null,
    debounceTimer: null,

    /**
     * Configuration Check
     */
    get useGoogleMaps() {
        const config = window.APP_CONFIG || {};
        const key = config.GOOGLE_MAPS_KEY;
        const isDev = config.ENV === 'development' || !key || key.includes('REPLACE') || key.length < 20;
        return !isDev;
    },

    /**
     * Entry point to open the map modal.
     */
    async open(arg1 = 'SERVICE', arg2 = null) {
        if (typeof arg1 === 'function') {
            this.mode = 'PICKER';
            this.callback = arg1;
        } else {
            this.mode = arg1;
            this.callback = arg2;
        }
        
        this.injectModal();
        const modal = document.getElementById('loc-picker-modal');
        if(modal) modal.classList.add('active');

        // Button Behavior Logic
        const manageBtn = document.getElementById('lp-manage-addrs');
        if (manageBtn) {
            manageBtn.style.display = 'block';
            if (this.mode === 'PICKER') {
                manageBtn.innerText = "Enter Address Manually";
                manageBtn.onclick = () => this.confirmPin(); 
            } else {
                manageBtn.innerText = "Manage addresses";
                this.bindManageButton();
            }
        }

        this.recoverLocation();

        if (this.useGoogleMaps) {
            await this.initGoogleMap();
        } else {
            await this.initLeafletMap();
        }
    },

    close() {
        const modal = document.getElementById('loc-picker-modal');
        if (modal) modal.classList.remove('active');
        
        if (this.leafletMap) {
            this.leafletMap.remove();
            this.leafletMap = null;
        }
        
        this.tempAddressData = null;
        this.callback = null;
    },

    // ---------------------------------------------------------
    // Maps Initialization
    // ---------------------------------------------------------
    async initGoogleMap() {
        if (!window.MapsLoader) return;
        
        try {
            await window.MapsLoader.load();
            const mapEl = document.getElementById('lp-map');
            if (!mapEl) return;

            this.googleMap = new google.maps.Map(mapEl, {
                center: this.tempCoords,
                zoom: 17,
                disableDefaultUI: true,
                gestureHandling: 'greedy'
            });

            this.geocoder = new google.maps.Geocoder();

            this.googleMap.addListener('idle', () => {
                const c = this.googleMap.getCenter();
                this.handleMapMove({ lat: c.lat(), lng: c.lng() });
            });

            this.reverseGeocode(this.tempCoords.lat, this.tempCoords.lng);

        } catch (e) {
            console.error("Google Maps Load Failed, falling back to OSM", e);
            this.initLeafletMap();
        }
    },

    async initLeafletMap() {
        if (!window.L) await this.loadLeafletLib();

        const mapEl = document.getElementById('lp-map');
        if (!mapEl) return;

        this.leafletMap = L.map(mapEl, { zoomControl: false }).setView(
            [this.tempCoords.lat, this.tempCoords.lng], 
            17
        );

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.leafletMap);

        this.leafletMap.on('moveend', () => {
            const c = this.leafletMap.getCenter();
            this.handleMapMove({ lat: c.lat, lng: c.lng });
        });

        this.reverseGeocode(this.tempCoords.lat, this.tempCoords.lng);
    },

    async loadLeafletLib() {
        return new Promise((resolve, reject) => {
            const css = document.createElement('link');
            css.rel = 'stylesheet';
            css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(css);

            const script = document.createElement('script');
            script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    },

    // ---------------------------------------------------------
    // Geocoding Logic
    // ---------------------------------------------------------
    
    handleMapMove(coords) {
        this.tempCoords = coords;
        clearTimeout(this.debounceTimer);
        
        const txt = document.getElementById('lp-address-text');
        if(txt) txt.innerText = "Locating...";
        
        this.debounceTimer = setTimeout(() => {
            this.reverseGeocode(coords.lat, coords.lng);
        }, 1000);
    },

    async reverseGeocode(lat, lng) {
        const btn = document.getElementById('lp-confirm-btn');
        const txt = document.getElementById('lp-address-text');
        if (btn) btn.disabled = true;

        try {
            if (this.useGoogleMaps && this.geocoder) {
                const response = await this.geocoder.geocode({ location: { lat, lng } });
                if (response.results[0]) {
                    this.setResultData(response.results[0], 'GOOGLE');
                }
            } else {
                const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`;
                const response = await fetch(url, { headers: { 'Accept-Language': 'en' } });
                if (!response.ok) throw new Error("Nominatim Error");
                const data = await response.json();
                this.setResultData(data, 'OSM');
            }
        } catch (e) {
            console.warn("Geocode failed", e);
            if (txt) txt.innerText = "Unknown Location (Pin Selected)";
            this.tempAddressData = { formatted_address: "Pinned Location" };
            if (btn) btn.disabled = false;
        }
    },

    setResultData(data, source) {
        const txt = document.getElementById('lp-address-text');
        const btn = document.getElementById('lp-confirm-btn');
        
        let formatted = '';
        let city = '';
        let pincode = '';

        if (source === 'GOOGLE') {
            formatted = data.formatted_address;
            data.address_components?.forEach(c => {
                if (c.types.includes('locality')) city = c.long_name;
                if (c.types.includes('postal_code')) pincode = c.long_name;
            });
        } else if (source === 'OSM') {
            formatted = data.display_name;
            const addr = data.address || {};
            city = addr.city || addr.town || addr.village || addr.county || '';
            pincode = addr.postcode || '';
        }

        this.tempAddressData = {
            formatted_address: formatted,
            city: city,
            pincode: pincode,
            source: source
        };

        if (txt) txt.innerText = formatted;
        if (btn) btn.disabled = false;
    },

    // ---------------------------------------------------------
    // ✅ NEW: ROBUST GPS LOGIC (Fixes Timeout Error)
    // ---------------------------------------------------------
    
    async detectRealLocation(isSilent = false) {
        if (!navigator.geolocation) {
            if(!isSilent && window.Toast) Toast.error("Geolocation not supported.");
            return;
        }

        // 1. UI Feedback: Start Spinner
        const btn = document.getElementById('lp-gps-btn');
        const icon = btn ? btn.querySelector('i') : null;
        if (icon) icon.className = 'fas fa-circle-notch fa-spin text-primary';

        try {
            // 2. Attempt 1: High Accuracy (GPS) with 5s Timeout
            // Fails fast if indoors to switch to fallback quicker
            const position = await this._getPosition({ 
                enableHighAccuracy: true, 
                timeout: 5000, 
                maximumAge: 0 
            });
            this._handleGpsSuccess(position, isSilent, icon);

        } catch (err) {
            console.warn("High Accuracy GPS failed, switching to fallback...", err.message);

            // 3. Attempt 2: Low Accuracy (Wifi/Network)
            // Much faster, rarely times out
            try {
                const position = await this._getPosition({ 
                    enableHighAccuracy: false, 
                    timeout: 10000, 
                    maximumAge: 0 
                });
                this._handleGpsSuccess(position, isSilent, icon);
            } catch (err2) {
                // 4. Final Failure
                this._handleGpsError(err2, isSilent, icon);
            }
        }
    },

    // Helper: Wrap Geolocation API in Promise
    _getPosition(options) {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, options);
        });
    },

    _handleGpsSuccess(pos, isSilent, icon) {
        const { latitude, longitude } = pos.coords;
        this.tempCoords = { lat: latitude, lng: longitude };
        
        // Update Map Center
        if (this.googleMap) {
            this.googleMap.panTo(this.tempCoords);
            this.googleMap.setZoom(17);
        } else if (this.leafletMap) {
            this.leafletMap.setView([latitude, longitude], 17);
        }
        
        // Fetch Address
        this.reverseGeocode(latitude, longitude);

        // Reset Icon
        if (icon) icon.className = 'fas fa-crosshairs text-primary';
        if (!isSilent && window.Toast) Toast.success("Location detected!");
    },

    _handleGpsError(err, isSilent, icon) {
        console.error("GPS Final Error", err);
        if (icon) icon.className = 'fas fa-crosshairs text-muted'; // Gray out
        
        if (!isSilent) {
            let msg = "Could not detect location.";
            if (err.code === 1) msg = "Permission Denied. Please enable location.";
            else if (err.code === 2) msg = "Location unavailable.";
            else if (err.code === 3) msg = "Location request timed out (Signal weak).";
            
            if (window.Toast) Toast.error(msg);
            else alert(msg);
        }
    },

    // ---------------------------------------------------------
    // Confirm & Cleanup
    // ---------------------------------------------------------

    confirmPin() {
        const addr = this.tempAddressData || { formatted_address: 'Pinned Location' };
        
        if (this.callback) {
            this.callback({
                lat: this.tempCoords.lat,
                lng: this.tempCoords.lng,
                address: addr.formatted_address,
                city: addr.city || '',
                pincode: addr.pincode || ''
            });
            this.close();
            return;
        }

        if (this.mode === 'SERVICE') {
            let area = addr.city || 'Pinned Location';
            if (addr.formatted_address) {
                const parts = addr.formatted_address.split(',');
                if (parts.length > 0) area = parts[0]; 
            }

            if (window.LocationManager) {
                window.LocationManager.setServiceLocation({
                    lat: this.tempCoords.lat,
                    lng: this.tempCoords.lng,
                    city: addr.city || 'Unknown',
                    area_name: area,
                    formatted_address: addr.formatted_address
                });
            }
            this.close();
        }
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
                
                <div class="map-container-wrapper" style="position: relative; flex: 1; width: 100%; height: 400px; background:#eee;">
                    <div id="lp-map" style="width: 100%; height: 100%; z-index:1;"></div>
                    
                    <div class="center-pin" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -100%); z-index: 500; pointer-events: none; display:flex; flex-direction:column; align-items:center;">
                         <i class="fas fa-map-marker-alt" style="font-size: 2.5rem; color: #ef4444; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3)); margin-bottom:-3px;"></i>
                         <div style="width:8px; height:4px; background:rgba(0,0,0,0.3); border-radius:50%;"></div>
                    </div>

                    <div id="lp-gps-btn" class="gps-btn" onclick="window.LocationPicker.detectRealLocation()" style="position:absolute; bottom:20px; right:20px; z-index:800; background:white; width:45px; height:45px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px rgba(0,0,0,0.2); cursor:pointer;">
                        <i class="fas fa-crosshairs text-primary"></i>
                    </div>
                </div>
                
                <div class="loc-footer">
                    <div id="lp-address-text" class="text-muted small mb-3 font-weight-bold" style="min-height:20px;">Fetching location...</div>
                    <button id="lp-confirm-btn" class="btn btn-primary w-100" onclick="window.LocationPicker.confirmPin()" disabled>
                        Confirm Location
                    </button>
                    <button id="lp-manage-addrs" class="btn btn-link w-100 mt-2" style="display:none">Manage addresses</button>
                </div>
            </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', html);
        
        const style = document.createElement('style');
        style.innerHTML = `.leaflet-control-attribution { font-size: 9px; opacity: 0.7; }`;
        document.head.appendChild(style);
        
        this.bindManageButton();
    },

    bindManageButton() {
        const btn = document.getElementById('lp-manage-addrs');
        if (btn) {
            btn.onclick = () => {
                const token = localStorage.getItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN);
                if (token) window.location.href = 'addresses.html';
                else {
                    alert("Please login to manage addresses");
                    window.location.href = 'auth.html';
                }
            };
        }
    },

    recoverLocation() {
        try {
            const ctx = JSON.parse(localStorage.getItem(window.APP_CONFIG?.STORAGE_KEYS?.SERVICE_CONTEXT) || 'null');
            if (ctx && ctx.lat) {
                this.tempCoords = { lat: parseFloat(ctx.lat), lng: parseFloat(ctx.lng) };
            }
        } catch(e) {}
    }
};