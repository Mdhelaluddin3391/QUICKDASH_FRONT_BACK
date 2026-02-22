/**
 * LocationManager: Centralized State Management (Final Production Version)
 * Handles L1 (Browsing) vs L2 (Delivery) Contexts & Multi-tab Sync.
 */
(function() {
    const LocationManager = {
        KEYS: {
            // L1: Browsing Context (GPS / Map Pin)
            SERVICE_CONTEXT: 'app_service_context', 
            // L2: Delivery Context (Actual Address ID)
            DELIVERY_CONTEXT: 'app_delivery_context' 
        },

        _get(key) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : null;
            } catch (e) {
                console.error("[LocationManager] Parse Error", e);
                return null;
            }
        },

        _set(key, data) {
            localStorage.setItem(key, JSON.stringify(data));
            
            // --- 🔥 SMART CACHE CLEAR ON LOCATION SET ---
            if (window.ApiService) {
                window.ApiService.clearCache();
            } else {
                sessionStorage.clear();
            }

            this._notifyChange();
        },

        /**
         * Set L1: Browsing Location
         * Used when user grants GPS or picks a location on the map (pre-login).
         * @param {Object} data - { lat, lng, area_name, city, formatted_address }
         */
        setServiceLocation(data) {
            if (!data || !data.lat || !data.lng) {
                console.error("[LocationManager] Invalid Service Data", data);
                return;
            }
            // Normalize
            const context = {
                lat: data.lat,
                lng: data.lng,
                city: data.city || '',
                area_name: data.area_name || data.formatted_address || 'Current Location',
                timestamp: Date.now()
            };
            this._set(this.KEYS.SERVICE_CONTEXT, context);
            console.log(`[LocationManager] Service Location Set: ${context.area_name}`);
        },

        /**
         * Set L2: Delivery Address
         * Used when user selects a saved address for checkout.
         * @param {Object} data - { id, lat, lng, address_line, city }
         */
        setDeliveryAddress(data) {
            if (!data || !data.id) {
                console.error("[LocationManager] Invalid Delivery Data", data);
                return;
            }
            // Normalize backend fields (latitude -> lat)
            const context = {
                id: data.id,
                lat: data.latitude || data.lat,
                lng: data.longitude || data.lng,
                city: data.city || '',
                label: data.label || 'Delivery',
                address_line: data.address_line || 'Selected Address',
                timestamp: Date.now()
            };
            this._set(this.KEYS.DELIVERY_CONTEXT, context);
            console.log(`[LocationManager] Delivery Address Set: ID ${context.id}`);
        },

        /**
         * Get Context for API Headers
         * Priority: L2 (Delivery) > L1 (Service)
         */
        getLocationContext() {
            const delivery = this._get(this.KEYS.DELIVERY_CONTEXT);
            const service = this._get(this.KEYS.SERVICE_CONTEXT);

            if (delivery && delivery.id) {
                return { 
                    type: 'L2', 
                    addressId: delivery.id, 
                    lat: delivery.lat, 
                    lng: delivery.lng 
                };
            }
            
            if (service && service.lat) {
                return { 
                    type: 'L1', 
                    lat: service.lat, 
                    lng: service.lng 
                };
            }

            return { type: 'NONE' };
        },

        /**
         * Get Display Info for UI (Navbar)
         */
        getDisplayLocation() {
            const delivery = this._get(this.KEYS.DELIVERY_CONTEXT);
            const service = this._get(this.KEYS.SERVICE_CONTEXT);

            if (delivery) {
                return {
                    type: 'DELIVERY',
                    label: delivery.label,
                    subtext: delivery.address_line,
                    is_active: true
                };
            }

            if (service) {
                return {
                    type: 'SERVICE',
                    label: service.area_name,
                    subtext: 'Browsing',
                    is_active: false
                };
            }

            return {
                type: 'NONE',
                label: 'Select Location',
                subtext: 'Location Required',
                is_active: false
            };
        },

        hasLocation() {
            return !!(this._get(this.KEYS.DELIVERY_CONTEXT) || this._get(this.KEYS.SERVICE_CONTEXT));
        },

        clear() {
            localStorage.removeItem(this.KEYS.SERVICE_CONTEXT);
            localStorage.removeItem(this.KEYS.DELIVERY_CONTEXT);
            
            // --- 🔥 SMART CACHE CLEAR ON LOCATION CLEAR ---
            if (window.ApiService) {
                window.ApiService.clearCache();
            } else {
                sessionStorage.clear();
            }

            this._notifyChange();
        },

        _notifyChange() {
            window.dispatchEvent(new CustomEvent('app:location-changed'));
        }
    };

    // Expose to window
    window.LocationManager = LocationManager;

    // Multi-Tab Sync: Reload if location changes in another tab to prevent ghost carts
    window.addEventListener('storage', (e) => {
        if (e.key === LocationManager.KEYS.DELIVERY_CONTEXT || e.key === LocationManager.KEYS.SERVICE_CONTEXT) {
            console.warn("[LocationManager] Syncing across tabs...");
            // --- 🔥 SMART CACHE CLEAR MULTI-TAB ---
            if (window.ApiService) { window.ApiService.clearCache(); } else { sessionStorage.clear(); }
            window.location.reload();
        }
    });

})();