/* assets/js/utils/service-check.js */

if (!window.ServiceCheck) {
    window.ServiceCheck = {
        async init() {
            // 1. CRITICAL: Check via LocationManager (Support for L1 & L2)
            if (window.LocationManager && window.LocationManager.hasLocation()) {
                console.log("[ServiceCheck] Location Context Found. Skipping modal.");
                return;
            }

            // Fallback: If LocationManager isn't loaded yet, check raw storage (safe guard)
            // But prefer strict LocationManager check
            if (localStorage.getItem('app_service_context') || localStorage.getItem('app_delivery_context')) {
                return;
            }

            // 2. Wait for Config (if needed)
            try {
                if (window.AppConfigService) await window.AppConfigService.load();
            } catch (e) { }

            // 3. Silent Permission Check (Browser API)
            if (navigator.permissions && navigator.permissions.query) {
                try {
                    const result = await navigator.permissions.query({ name: 'geolocation' });
                    if (result.state === 'granted') {
                        console.log("Location permission granted. Fetching silently...");
                        this.detectGPS(true); // Silent Mode
                        return;
                    }
                } catch (e) {
                    console.warn("Permission API error", e);
                }
            }

            // 4. Show Modal if no location & no permission
            this.renderPermissionModal();
        },

        renderPermissionModal() {
            if (document.getElementById('service-modal')) return;

            const div = document.createElement('div');
            div.id = 'service-modal';
            div.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(3px);`;

            div.innerHTML = `
                <div style="background:#fff;padding:30px;border-radius:16px;text-align:center;max-width:400px;width:90%;box-shadow:0 10px 25px rgba(0,0,0,0.2);position:relative;">
                    <button id="btn-close-modal" style="position:absolute; top:15px; right:15px; background:transparent; border:none; font-size:24px; color:#555; cursor:pointer; z-index:10; padding:5px;">
                        <i class="fas fa-times"></i>
                    </button>
                    <div style="background:#f0fdf4;width:80px;height:80px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;">
                        <i class="fas fa-map-marked-alt fa-3x" style="color:#2ecc71;"></i>
                    </div>
                    <h3>Delivery Location</h3>
                    <p class="text-muted mb-4">Set your location to see accurate prices and delivery time.</p>
                    <button id="btn-grant" class="btn btn-primary w-100 py-3 mb-2" style="font-weight:600;">
                        <i class="fas fa-crosshairs me-2"></i> Enable Location
                    </button>
                    <button id="btn-manual" class="btn btn-outline-secondary w-100 py-2 mb-2">Select Manually</button>
                    <button id="btn-skip" class="btn btn-link text-muted w-100" style="text-decoration:none; font-size:0.9rem;">
                        Skip for now
                    </button>
                </div>
            `;
            document.body.appendChild(div);

            document.getElementById('btn-grant').onclick = () => this.detectGPS(false);
            document.getElementById('btn-manual').onclick = () => {
                document.getElementById('service-modal').remove();
                if (window.LocationPicker) LocationPicker.open('SERVICE');
            };
            const closeAction = () => document.getElementById('service-modal').remove();
            document.getElementById('btn-close-modal').onclick = closeAction;
            document.getElementById('btn-skip').onclick = closeAction;
        },

        detectGPS(isSilent = false) {
            if (!navigator.geolocation) {
                if (!isSilent && window.Toast) Toast.error("Geolocation is not supported.");
                return;
            }

            const btn = document.getElementById('btn-grant');
            if (btn) { btn.innerText = "Locating..."; btn.disabled = true; }

            navigator.geolocation.getCurrentPosition(
                async (pos) => {
                    const { latitude, longitude } = pos.coords;
                    await this.handleLocationSuccess(latitude, longitude);
                },
                (err) => {
                    console.error("Geolocation Error:", err);

                    // If silent check failed (timeout/GPS off), show modal to ask user
                    if (isSilent) {
                        console.log("Silent detection failed, showing modal.");
                        this.renderPermissionModal();
                        return;
                    }

                    if (btn) { btn.innerText = "Retry Location"; btn.disabled = false; }

                    if (err.code === 1 && (err.message.includes("secure origin") || err.message.includes("SSL"))) {
                        alert("⚠️ Development Mode Warning\n\nHTTP blocks location. Using Default (Bengaluru).");
                        this.handleLocationSuccess(12.9716, 77.5946, true);
                        return;
                    }

                    let msg = "Location access denied.";
                    if (err.code === 2) msg = "GPS Signal weak.";
                    else if (err.code === 3) msg = "Location timed out.";

                    if (window.Toast) Toast.error(msg + " Please select manually.");
                },
                // Increased timeout to 20 seconds (20000ms) to allow slow GPS lock
                { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
            );
        },

        async handleLocationSuccess(lat, lng, isFallback = false) {
            try {
                let city = 'Bengaluru';
                let area = 'Current Location';
                let fmt = 'GPS Location';

                // Reverse Geocode if Google Maps is available
                if (!isFallback && window.APP_CONFIG && window.APP_CONFIG.GOOGLE_MAPS_KEY) {
                    try {
                        if (window.MapsLoader) await window.MapsLoader.load();
                        const geocoder = new google.maps.Geocoder();
                        const response = await geocoder.geocode({ location: { lat, lng } });

                        if (response.results[0]) {
                            const r = response.results[0];
                            fmt = r.formatted_address;
                            r.address_components.forEach(c => {
                                if (c.types.includes('locality')) city = c.long_name;
                                if (c.types.includes('sublocality') || c.types.includes('neighborhood')) area = c.long_name;
                            });
                        }
                    } catch (e) { console.warn("Geocode skipped", e); }
                }

                // INTEGRATION: Use LocationManager to save L1 Context
                if (window.LocationManager) {
                    window.LocationManager.setServiceLocation({
                        lat: lat, 
                        lng: lng, 
                        city: city, 
                        area_name: area, 
                        formatted_address: fmt
                    });
                } else {
                    console.error("LocationManager missing during ServiceCheck!");
                }

                const modal = document.getElementById('service-modal');
                if (modal) modal.remove();

                setTimeout(() => window.location.reload(), 500);

            } catch (e) {
                console.error("Location Logic Error", e);
                if (window.Toast) Toast.error("Failed to set location.");
            }
        }
    };
}