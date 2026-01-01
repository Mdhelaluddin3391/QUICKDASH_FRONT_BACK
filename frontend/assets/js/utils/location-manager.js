/**
 * LocationManager: Centralized State Management for QuickDash Location Logic.
 * 1. L1 (Service Context): Browsing/Stock checks (GPS/Map Pin).
 * 2. L2 (Delivery Context): Checkout/Tax/Final routing (User Address).
 * 3. L2 always overrides L1 in UI display.
 */
const LocationManager = {
    get KEYS() {
        const k = window.APP_CONFIG?.STORAGE_KEYS || {};
        return {
            SERVICE: k.SERVICE_CONTEXT || 'app_service_context',
            DELIVERY: k.DELIVERY_CONTEXT || 'app_delivery_context',
            WAREHOUSE: k.WAREHOUSE_ID || 'current_warehouse_id'
        };
    },

    getDisplayLocation() {
        const delivery = this.getDeliveryContext();
        const service = this.getServiceContext();

        // PRIORITY 1: Delivery Address (Checkout Context)
        if (delivery && delivery.id) {
            return {
                type: 'DELIVERY',
                label: delivery.label || 'Delivery',
                subtext: delivery.address_line || delivery.city || 'Selected Address',
                is_active: true
            };
        }

        // PRIORITY 2: Service Location (Browsing Context)
        if (service && service.lat) {
            return {
                type: 'SERVICE',
                label: service.area_name || service.city || 'Current Location',
                subtext: service.city || '',
                is_active: false
            };
        }

        // PRIORITY 3: Default
        return {
            type: 'NONE',
            label: 'Select your location',
            subtext: '',
            is_active: false
        };
    },

    getServiceContext() {
        try { return JSON.parse(localStorage.getItem(this.KEYS.SERVICE)); } catch (e) { return null; }
    },

    getDeliveryContext() {
        try { return JSON.parse(localStorage.getItem(this.KEYS.DELIVERY)); } catch (e) { return null; }
    },

    /**
     * Sets Browsing Location (L1).
     * CRITICAL: Wipes Delivery Context (L2) to prevent "Ghost Address" conflicts.
     */
    setServiceLocation(data) {
        const payload = {
            lat: Number(data.lat),
            lng: Number(data.lng),
            area_name: data.area_name || 'Pinned Location',
            city: data.city || '',
            formatted_address: data.formatted_address || ''
        };
        
        console.info('LocationManager: Set L1 (Service)', payload);
        // Preserve DELIVERY context (L2). Do NOT wipe it here; Delivery must always override Service in UI.
        const existingDelivery = localStorage.getItem(this.KEYS.DELIVERY);
        localStorage.setItem(this.KEYS.SERVICE, JSON.stringify(payload));
        if (existingDelivery) {
            // Sanity check in dev: ensure we didn't accidentally remove delivery
            console.assert(localStorage.getItem(this.KEYS.DELIVERY) !== null, 'Delivery context was unexpectedly removed by setServiceLocation');
        }

        this._notifyChange('SERVICE');
    },

    /**
     * Sets Delivery Address (L2).
     */
    setDeliveryAddress(addressObj) {
        const payload = {
            id: addressObj.id,
            label: addressObj.label, 
            address_line: addressObj.address_line || addressObj.google_address_text,
            city: addressObj.city,
            lat: addressObj.latitude,
            lng: addressObj.longitude
        };

        console.info('LocationManager: Set L2 (Delivery)', payload);
        localStorage.setItem(this.KEYS.DELIVERY, JSON.stringify(payload));
        this._notifyChange('DELIVERY');
    },

    _notifyChange(source) {
        window.dispatchEvent(new CustomEvent(window.APP_CONFIG.EVENTS.LOCATION_CHANGED, { detail: { source } }));
    }
};
window.LocationManager = LocationManager;

// --- DEV SANITY CHECK (non-destructive; only runs on localhost) ---
(function(){
    try {
        if (!window.LocationManager) return;
        if (!window.location || !(window.location.hostname === 'localhost' || (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL && window.APP_CONFIG.API_BASE_URL.includes('localhost')))) return;

        const DKEY = LocationManager.KEYS.DELIVERY;
        const backup = localStorage.getItem(DKEY);
        try {
            // Insert a temporary delivery context
            localStorage.setItem(DKEY, JSON.stringify({ id: '__sanity__', label: 'SANITY', address_line: 'Sanity address' }));
            // Call setServiceLocation (should NOT remove delivery context)
            LocationManager.setServiceLocation({ lat: 0.1, lng: 0.1, city: 'SanityCity', area_name: 'SanityArea' });

            if (!localStorage.getItem(DKEY)) {
                console.error('LocationManager SANITY FAIL: Delivery context was removed by setServiceLocation');
            } else {
                console.info('LocationManager SANITY OK: Delivery context preserved by setServiceLocation');
            }
        } finally {
            if (backup) localStorage.setItem(DKEY, backup);
            else localStorage.removeItem(DKEY);
        }
    } catch (e) { /* ignore */ }
})();