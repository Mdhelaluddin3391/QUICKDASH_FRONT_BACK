(function () {
    // Priority: Injected Env (Docker/Local) > Global Var > Default Production
    const envApiBase = (window.env && window.env.API_BASE_URL) ? window.env.API_BASE_URL : null;
    const defaultApiBase = "https://quickdash-front-back.onrender.com/api/v1";
    
    const apiBase = envApiBase || defaultApiBase;

    window.APP_CONFIG = {
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

    window.APP_CONFIG.STATIC_BASE = (document.querySelector('base') && document.querySelector('base').href) ? document.querySelector('base').href : '/';

    window.AppConfigService = {
        isLoaded: false,

        async load() {
            if (this.isLoaded) return;

            try {
                const configUrl = `${window.APP_CONFIG.API_BASE_URL.replace('/v1', '')}/config/`;

                let response = null;
                try {
                    response = await fetch(configUrl);
                } catch (err) {
                    console.warn("Backend config fetch failed, using defaults");
                }

                if (response && response.ok) {
                    const data = await response.json();
                    if (data.keys && data.keys.google_maps) {
                        window.APP_CONFIG.GOOGLE_MAPS_KEY = data.keys.google_maps;
                    }
                    this.isLoaded = true;
                    return;
                }
                
                // Fallback to local config
                const localConfigUrl = '/config.local.json';
                try {
                    const localResp = await fetch(localConfigUrl);
                    if(localResp.ok) {
                         const data = await localResp.json();
                         if (data.keys) window.APP_CONFIG.GOOGLE_MAPS_KEY = data.keys.google_maps;
                    }
                } catch(e) {}

                this.isLoaded = true;

            } catch (e) {
                console.error("Config load error", e);
            }
        }
    };
})();