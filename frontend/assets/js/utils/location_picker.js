/* frontend/assets/js/utils/location_picker.js */

window.LocationPicker = {
    mode: 'SERVICE',
    
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
     * Returns TRUE if we should use Google Maps (Prod + Valid Key).
     * Returns FALSE for Dev/OpenStreetMap.
     */
    get useGoogleMaps() {
        const config = window.APP_CONFIG || {};
        const key = config.GOOGLE_MAPS_KEY;
        // Check for specific ENV flag OR if the key is a dummy/missing
        const isDev = config.ENV === 'development' || !key || key.includes('REPLACE') || key.length < 20;
        return !isDev;
    },

    /**
     * Entry point to open the map modal.
     */
    async open(arg1 = 'SERVICE', arg2 = null) {
        // Handle Arguments (Mode vs Callback)
        if (typeof arg1 === 'function') {
            this.mode = 'PICKER';
            this.callback = arg1;
        } else {
            this.mode = arg1;
            this.callback = arg2;
        }
        
        // 1. Inject UI Modal
        this.injectModal();
        const modal = document.getElementById('loc-picker-modal');
        if(modal) modal.classList.add('active');

        // Show "Manage Addresses" button
        const manageBtn = document.getElementById('lp-manage-addrs');
        if (manageBtn) manageBtn.style.display = 'block';

        // 2. Recover Last Known Location
        this.recoverLocation();

        // 3. Initialize the appropriate Map Provider
        if (this.useGoogleMaps) {
            await this.initGoogleMap();
        } else {
            await this.initLeafletMap();
        }

        // 4. "Real Lat/Lng": If using default coords, try to fetch GPS
        if (this.isDefaultLocation(this.tempCoords)) {
            this.detectRealLocation();
        }
    },

    close() {
        const modal = document.getElementById('loc-picker-modal');
        if (modal) modal.classList.remove('active');
        
        // Cleanup Leaflet instance to prevent "Map already initialized" error
        if (this.leafletMap) {
            this.leafletMap.remove();
            this.leafletMap = null;
        }
        
        this.tempAddressData = null;
        this.callback = null;
    },

    // ---------------------------------------------------------
    // Strategy 1: Google Maps (Production)
    // ---------------------------------------------------------
    async initGoogleMap() {
        if (!window.MapsLoader) return;
        
        try {
            await window.MapsLoader.load();
            const mapEl = document.getElementById('lp-map');
            if (!mapEl) return;

            // Initialize Google Map
            this.googleMap = new google.maps.Map(mapEl, {
                center: this.tempCoords,
                zoom: 17,
                disableDefaultUI: true,
                gestureHandling: 'greedy'
            });

            this.geocoder = new google.maps.Geocoder();

            // Bind Events
            this.googleMap.addListener('idle', () => {
                const c = this.googleMap.getCenter();
                this.handleMapMove({ lat: c.lat(), lng: c.lng() });
            });

            // Initial Geocode
            this.reverseGeocode(this.tempCoords.lat, this.tempCoords.lng);

        } catch (e) {
            console.error("Google Maps Load Failed, falling back to OSM", e);
            this.initLeafletMap(); // Failover
        }
    },

    // ---------------------------------------------------------
    // Strategy 2: Leaflet + OpenStreetMap (Development)
    // ---------------------------------------------------------
    async initLeafletMap() {
        // Ensure Leaflet Library is loaded
        if (!window.L) await this.loadLeafletLib();

        const mapEl = document.getElementById('lp-map');
        if (!mapEl) return;

        // Initialize Leaflet
        this.leafletMap = L.map(mapEl, { zoomControl: false }).setView(
            [this.tempCoords.lat, this.tempCoords.lng], 
            17
        );

        // Add OSM Tile Layer (Free, No Key)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.leafletMap);

        // Bind Events (Simulate "Idle" using "moveend")
        this.leafletMap.on('moveend', () => {
            const c = this.leafletMap.getCenter();
            this.handleMapMove({ lat: c.lat, lng: c.lng });
        });

        // Initial Geocode
        this.reverseGeocode(this.tempCoords.lat, this.tempCoords.lng);
    },

    /**
     * Dynamically loads Leaflet for pages that don't have it (like addresses.html)
     */
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
    // Core Logic (Provider Agnostic)
    // ---------------------------------------------------------
    
    handleMapMove(coords) {
        this.tempCoords = coords;
        // Debounce API calls (1 second) to respect Nominatim Rate Limits
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
                // --- GOOGLE STRATEGY ---
                const response = await this.geocoder.geocode({ location: { lat, lng } });
                if (response.results[0]) {
                    this.setResultData(response.results[0], 'GOOGLE');
                }
            } else {
                // --- OPENSTREETMAP STRATEGY (NOMINATIM) ---
                // Best Practice: Send User-Agent/Email if possible, but browser limits headers.
                const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`;
                
                const response = await fetch(url, {
                    headers: { 'Accept-Language': 'en' } // Prefer English
                });
                if (!response.ok) throw new Error("Nominatim Error");
                
                const data = await response.json();
                this.setResultData(data, 'OSM');
            }
        } catch (e) {
            console.warn("Geocode failed", e);
            if (txt) txt.innerText = "Unknown Location (Pin Selected)";
            // Still allow confirming coordinates even if address lookup fails
            this.tempAddressData = { formatted_address: "Pinned Location" };
            if (btn) btn.disabled = false;
        }
    },

    /**
     * Normalizes data from Google or OSM into a standard internal format
     */
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
            // Nominatim city mapping is complex
            city = addr.city || addr.town || addr.village || addr.county || '';
            pincode = addr.postcode || '';
        }

        // Store Normalized Data
        this.tempAddressData = {
            formatted_address: formatted,
            city: city,
            pincode: pincode,
            source: source
        };

        if (txt) txt.innerText = formatted;
        if (btn) btn.disabled = false;
    },

    /**
     * Uses Browser Geolocation API to find real user location.
     */
    detectRealLocation() {
        if (!navigator.geolocation) return;

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const { latitude, longitude } = pos.coords;
                this.tempCoords = { lat: latitude, lng: longitude };
                
                // Move Map Center
                if (this.googleMap) {
                    this.googleMap.panTo(this.tempCoords);
                } else if (this.leafletMap) {
                    this.leafletMap.setView([latitude, longitude], 17);
                }
                
                // Trigger Geocode immediately
                this.reverseGeocode(latitude, longitude);
            },
            (err) => console.warn("GPS Denied", err),
            { enableHighAccuracy: true, timeout: 5000 }
        );
    },

    confirmPin() {
        const addr = this.tempAddressData || { formatted_address: 'Pinned Location' };
        
        // 1. Handle Callback Mode (e.g. from Add Address form)
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

        // 2. Handle Service Mode (Browsing Context)
        if (this.mode === 'SERVICE') {
            let area = addr.city || 'Pinned Location';
            
            // Extract short area name for Navbar
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

    // --- Utility Methods ---

    injectModal() {
        if (document.getElementById('loc-picker-modal')) return;

        // Note: The center pin is a pure CSS overlay, works for both Maps
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

                    <div class="gps-btn" onclick="window.LocationPicker.detectRealLocation()" style="position:absolute; bottom:20px; right:20px; z-index:800; background:white; width:45px; height:45px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 10px rgba(0,0,0,0.2); cursor:pointer;">
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
        
        // Add minimal CSS for Leaflet if needed (usually handled by loadLeafletLib)
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
    },

    isDefaultLocation(coords) {
        return Math.abs(coords.lat - 12.9716) < 0.0001 && Math.abs(coords.lng - 77.5946) < 0.0001;
    }
};