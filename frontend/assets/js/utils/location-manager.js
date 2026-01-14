/**
 * LocationManager: Centralized State Management (Architecture v2.0)
 * Fixed: Added missing setServiceLocation and setDeliveryAddress methods
 */
const LocationManager = {
    KEYS: {
        LAT: 'app_lat',
        LNG: 'app_lng',
        ADDRESS_ID: 'app_address_id',
        ADDRESS_TEXT: 'app_address_text' // For UI display only
    },

    /**
     * Set Location (Universal Core Logic)
     * - If addressId is provided, it's L2 (Delivery Mode).
     * - If only lat/lng, it's L1 (Browsing Mode).
     */
    setLocation(lat, lng, addressText = '', addressId = null) {
        if(!lat || !lng) {
            console.error("LocationManager: Invalid coordinates provided", lat, lng);
            return;
        }

        localStorage.setItem(this.KEYS.LAT, lat);
        localStorage.setItem(this.KEYS.LNG, lng);
        
        if (addressText) {
            localStorage.setItem(this.KEYS.ADDRESS_TEXT, addressText);
        }
        
        if (addressId) {
            localStorage.setItem(this.KEYS.ADDRESS_ID, addressId);
        } else {
            localStorage.removeItem(this.KEYS.ADDRESS_ID); // Switch to L1 (Browsing)
        }

        console.log(`Location Set: ${lat}, ${lng} (ID: ${addressId || 'None'})`);

        // Dispatch event for UI updates (Navbar, Cart)
        // Using a safe fallback string if APP_CONFIG isn't loaded yet
        const evtName = (window.APP_CONFIG && window.APP_CONFIG.EVENTS && window.APP_CONFIG.EVENTS.LOCATION_CHANGED) 
                        ? window.APP_CONFIG.EVENTS.LOCATION_CHANGED 
                        : 'app:location-changed';
                        
        window.dispatchEvent(new CustomEvent(evtName, {
            detail: { lat, lng, addressId }
        }));
    },

    /**
     * ✅ ADDED THIS FUNCTION (Fixes your console error)
     * Used by location_picker.js when GPS or Map is used.
     */
    setServiceLocation(data) {
        // Handle data coming from Google Maps or GPS fallback
        const text = data.formatted_address || data.area_name || 'Current Location';
        // Pass null as addressId strictly for Service Mode (Browsing)
        this.setLocation(data.lat, data.lng, text, null);
    },

    /**
     * ✅ ADDED THIS FUNCTION (Future proofing)
     * Used when selecting a saved address during checkout.
     */
    setDeliveryAddress(data) {
        // Handle potential naming differences (backend usually sends 'latitude', frontend uses 'lat')
        const lat = data.latitude || data.lat;
        const lng = data.longitude || data.lng;
        // Pass address ID strictly for Delivery Mode
        this.setLocation(lat, lng, data.address_line, data.id);
    },

    /**
     * Returns context for ApiService Headers
     */
    getLocationContext() {
        const lat = localStorage.getItem(this.KEYS.LAT);
        const lng = localStorage.getItem(this.KEYS.LNG);
        const addressId = localStorage.getItem(this.KEYS.ADDRESS_ID);

        if (addressId) {
            return { type: 'L2', addressId, lat, lng };
        } else if (lat && lng) {
            return { type: 'L1', lat, lng };
        }
        return { type: 'NONE' };
    },

    /**
     * For UI Components (Navbar, Address Picker)
     */
    getDisplayLocation() {
        const addressId = localStorage.getItem(this.KEYS.ADDRESS_ID);
        const addressText = localStorage.getItem(this.KEYS.ADDRESS_TEXT);
        const lat = localStorage.getItem(this.KEYS.LAT);

        // PRIORITY 1: Delivery Context (L2)
        if (addressId) {
            return {
                type: 'DELIVERY',
                label: 'Delivery to',
                subtext: addressText || 'Selected Address',
                is_active: true,
                id: addressId
            };
        }

        // PRIORITY 2: Service Context (L1)
        if (lat) {
            return {
                type: 'SERVICE',
                label: 'Browsing in',
                subtext: addressText || 'Current Location',
                is_active: false
            };
        }

        // PRIORITY 3: None
        return {
            type: 'NONE',
            label: 'Select Location',
            subtext: '',
            is_active: false
        };
    },

    hasLocation() {
        return !!localStorage.getItem(this.KEYS.LAT);
    },

    clearLocation() {
        Object.values(this.KEYS).forEach(key => localStorage.removeItem(key));
        window.location.reload();
    }
};

// MULTI-TAB SYNC
// If user changes location in Tab A, Tab B will auto-reload to prevent Ghost Carts.
window.addEventListener('storage', (e) => {
    if (e.key === LocationManager.KEYS.ADDRESS_ID || e.key === LocationManager.KEYS.LAT) {
        console.warn("Location changed in another tab. Syncing...");
        window.location.reload(); 
    }
});

// Expose to window
window.LocationManager = LocationManager;