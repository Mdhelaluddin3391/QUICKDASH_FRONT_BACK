// frontend/assets/js/config.js

(function () {
    
    const apiBase = "https://quickdash-front-back.onrender.com/api/v1";


    window.APP_CONFIG = {
        // The API_BASE_URL is now set directly from the constant above.
        API_BASE_URL: apiBase,
        TIMEOUT: 15000,
        GOOGLE_MAPS_KEY: null,
        ROUTES: {
            HOME: '/index.html',
            LOGIN: '/auth.html',
            CART: '/cart.html',
            CHECKOUT: '/checkout.html',
            PROFILE: '/profile.html',
            SUCCESS: '/success.html'
        },
        STORAGE_KEYS: {
            TOKEN: 'access_token',
            REFRESH: 'refresh_token',
            USER: 'user_data',
            WAREHOUSE_ID: 'current_warehouse_id',
            SERVICE_CONTEXT: 'app_service_context',
            DELIVERY_CONTEXT: 'app_delivery_context'
        },
        EVENTS: {
            LOCATION_CHANGED: 'app:location-changed',
            CART_UPDATED: 'cart-updated'
        }
    };

    // STATIC_BASE is derived from <base> if present, otherwise '/'
    window.APP_CONFIG.STATIC_BASE = (document.querySelector('base') && document.querySelector('base').href) ? document.querySelector('base').href : '/';

    window.AppConfigService = {
        isLoaded: false,

        async load() {
            if (this.isLoaded) return;

            try {
                // Construct config URL from the determined API Base
                const configUrl = `${window.APP_CONFIG.API_BASE_URL.replace('/v1', '')}/config/`;

                let response = null;
                try {
                    response = await fetch(configUrl);
                } catch (err) {
                    response = null;
                }

                if (response && response.ok) {
                    const data = await response.json();
                    if (data.keys && data.keys.google_maps) {
                        window.APP_CONFIG.GOOGLE_MAPS_KEY = data.keys.google_maps;
                    }
                    this.isLoaded = true;
                    console.log("App Config Loaded Successfully");
                    return;
                }

                // Try local fallback config (use Asset if present to resolve paths)
                const localConfigUrl = (window.Asset && window.Asset.url) ? window.Asset.url('config.local.json') : new URL('config.local.json', window.location.href).href;
                try {
                    const localResp = await fetch(localConfigUrl);
                    if (localResp && localResp.ok) {
                        const data = await localResp.json();
                        if (data.keys && data.keys.google_maps) {
                            window.APP_CONFIG.GOOGLE_MAPS_KEY = data.keys.google_maps;
                        }
                        this.isLoaded = true;
                        console.warn('App Config: Loaded local fallback config (config.local.json).');
                        return;
                    }
                } catch (err) {
                    // ignore local fallback failure
                }

                throw new Error(`Config fetch failed${response ? ' with status ' + response.status : ''}`);

            } catch (e) {
                console.error("CRITICAL: Failed to load app config. Some features may not work.", e.message);
            }
        }
    };
})();