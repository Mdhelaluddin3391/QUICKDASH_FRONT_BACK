/**
 * Centralized API Service (Production Hardened)
 * - Auto-injects Authorization headers
 * - Handles 401 Token Refresh automatically
 * - Injects Idempotency-Key for mutating requests
 * - Centralized Error Handling
 */
(function () {
    // Use a plain global object to avoid class/static issues in older browsers
    const ApiService = {
        isRefreshing: false,
        refreshSubscribers: [],

        // Generate UUIDv4 for Idempotency
        uuidv4: function () {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
                const r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        },

        getHeaders: function (uploadFile = false, method = 'GET') {
            const headers = {};
            if (!uploadFile) {
                headers['Content-Type'] = 'application/json';
            }

            const token = localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN);
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            // [AUDIT FIX] Idempotency for mutating methods
            if (['POST', 'PUT', 'PATCH'].includes(method.toUpperCase())) {
                headers['Idempotency-Key'] = ApiService.uuidv4();
            }

            return headers;
        },

        request: async function (endpoint, method = 'GET', body = null, isRetry = false) {
            // Defensive: ensure endpoint is a string
            endpoint = typeof endpoint === 'string' ? endpoint : String(endpoint || '/');

            // Ensure endpoint starts with /
            const safeEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
            const url = `${APP_CONFIG.API_BASE_URL}${safeEndpoint}`;

            const options = {
                method,
                headers: ApiService.getHeaders(false, method),
            };

            if (body) {
                // Keep behavior identical: JSON body for non-upload
                options.body = JSON.stringify(body);
            }

            try {
                const response = await fetch(url, options);

                // [AUDIT FIX] Handle 401 Unauthorized (Token Refresh Flow)
                if (response.status === 401 && !isRetry) {
                    if (ApiService.isRefreshing) {
                        // If already refreshing, queue this request
                        return new Promise((resolve) => {
                            ApiService.refreshSubscribers.push(() => {
                                resolve(ApiService.request(endpoint, method, body, true));
                            });
                        });
                    }

                    ApiService.isRefreshing = true;
                    const success = await ApiService.refreshToken();
                    ApiService.isRefreshing = false;

                    if (success) {
                        ApiService.onRefreshed();
                        return ApiService.request(endpoint, method, body, true);
                    } else {
                        // Refresh failed - Handle Session Expiry smartly
                        ApiService.handleAuthFailure();
                        return; // Stop execution
                    }
                }

                // Read response safely to handle empty or non-JSON bodies
                const text = await response.text();
                let data;
                try {
                    data = text ? JSON.parse(text) : null;
                } catch (parseErr) {
                    data = text;
                }

                if (!response.ok) {
                    let errorMsg = 'An unexpected error occurred';

                    if (data) {
                        if (data.detail) {
                            errorMsg = data.detail;
                        } else if (data.error) {
                            errorMsg = typeof data.error === 'object' ? JSON.stringify(data.error) : data.error;
                        } else if (data.non_field_errors) {
                            errorMsg = data.non_field_errors[0];
                        } else {
                            const keys = Object.keys(data);
                            if (keys.length > 0) {
                                const firstKey = keys[0];
                                const firstErr = Array.isArray(data[firstKey]) ? data[firstKey][0] : data[firstKey];
                                errorMsg = `${firstKey}: ${firstErr}`;
                            }
                        }
                    }

                    throw new Error(errorMsg);
                }

                return data === null ? {} : data;

            } catch (error) {
                if (window.location.hostname === 'localhost') {
                    console.error(`API Error [${method} ${endpoint}]:`, error);
                }
                throw error;
            }
        },

        refreshToken: async function () {
            const refresh = localStorage.getItem(APP_CONFIG.STORAGE_KEYS.REFRESH);
            if (!refresh) return false;

            try {
                const response = await fetch(`${APP_CONFIG.API_BASE_URL}/auth/refresh/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh })
                });

                if (response.ok) {
                    const data = await response.json();
                    localStorage.setItem(APP_CONFIG.STORAGE_KEYS.TOKEN, data.access);
                    if (data.refresh) {
                        localStorage.setItem(APP_CONFIG.STORAGE_KEYS.REFRESH, data.refresh);
                    }
                    return true;
                }
            } catch (e) {
                console.warn("Token refresh failed", e);
            }
            return false;
        },

        onRefreshed: function () {
            ApiService.refreshSubscribers.forEach((callback) => callback());
            ApiService.refreshSubscribers = [];
        },

        /**
         * Smart Logout: 
         * If on a public page (Home, Search), just clear token and reload (Guest Mode).
         * If on a private page (Profile, Checkout), redirect to Login.
         */
        handleAuthFailure: function() {
            // 1. Clear Stale Data
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.TOKEN);
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.REFRESH);
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.USER);

            // 2. Determine Page Type
            const currentPath = window.location.pathname;
            const privatePages = [
                '/profile.html', '/orders.html', '/checkout.html',
                '/addresses.html', '/order_detail.html', '/track_order.html'
            ];

            const isPrivate = privatePages.some(page => currentPath.includes(page));

            if (isPrivate) {
                window.location.href = APP_CONFIG.ROUTES.LOGIN;
            } else {
                console.warn("Session expired on public page.");

                // [FIX] Use sessionStorage instead of window variable
                // This persists across the reload so the loop actually stops.
                if (!sessionStorage.getItem('auth_reload_lock')) {
                    sessionStorage.setItem('auth_reload_lock', 'true');
                    console.warn("Attempting one-time recovery reload...");
                    try {
                        window.location.reload();
                    } catch (e) {
                        console.warn("Reload failed", e);
                    }
                } else {
                    console.warn("Reload already attempted; skipping to prevent loop.");
                    // Optional: Clear the lock after 10 seconds so normal usage isn't broken forever
                    setTimeout(() => sessionStorage.removeItem('auth_reload_lock'), 10000);
                }
            }
        },

        // Public shortcut methods (preserve names and behavior)
        get: function (endpoint) { return this.request(endpoint, 'GET'); },
        post: function (endpoint, body) { return this.request(endpoint, 'POST', body); },
        put: function (endpoint, body) { return this.request(endpoint, 'PUT', body); },
        patch: function (endpoint, body) { return this.request(endpoint, 'PATCH', body); },
        delete: function (endpoint) { return this.request(endpoint, 'DELETE'); }
    };

    window.ApiService = ApiService;
})();