/**
 * Centralized API Service (Production Hardened)
 * - Auto-injects Authorization headers
 * - Handles 401 Token Refresh automatically
 * - Injects Location Context (L1/L2) for Backend Middleware
 * - Injects Idempotency-Key for mutating requests
 * - Centralized Error Handling
 */
(function () {
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

        /**
         * INJECTS HEADERS
         * 1. Auth Token
         * 2. Idempotency Key
         * 3. Location Context (Critical for Backend Warehouse Resolution)
         */
        getHeaders: function (uploadFile = false, method = 'GET') {
            const headers = {};
            if (!uploadFile) {
                headers['Content-Type'] = 'application/json';
            }

            // 1. Auth Token
            const token = localStorage.getItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token');
            if (token && token !== 'null' && token !== 'undefined') {
                headers['Authorization'] = `Bearer ${token}`;
            }

            // 2. Idempotency
            if (['POST', 'PUT', 'PATCH'].includes(method.toUpperCase())) {
                headers['Idempotency-Key'] = ApiService.uuidv4();
            }

            // 3. LOCATION CONTEXT INJECTION (New Architecture)
            // Checks for L2 (Delivery Address) first, then L1 (GPS)
            if (window.LocationManager) {
                const locContext = window.LocationManager.getLocationContext();

                if (locContext.type === 'L2' && locContext.addressId) {
                    headers['X-Address-ID'] = locContext.addressId.toString();
                } 
                
                if (locContext.lat && locContext.lng) {
                    headers['X-Location-Lat'] = locContext.lat.toString();
                    headers['X-Location-Lng'] = locContext.lng.toString();
                }
            }

            return headers;
        },

        request: async function (endpoint, method = 'GET', body = null, isRetry = false) {
            // Ensure endpoint format
            const baseUrl = window.APP_CONFIG?.API_BASE_URL || '/api/v1';
            const safeEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
            const url = `${baseUrl}${safeEndpoint}`;

            const options = {
                method,
                headers: ApiService.getHeaders(false, method),
            };

            if (body) {
                options.body = JSON.stringify(body);
            }

            try {
                const response = await fetch(url, options);

                // [Global Handler] Location/Cart Mismatch (Architecture Step 8)
                if (response.status === 409) {
                    const resData = await response.clone().json().catch(() => ({}));
                    if (resData.code === 'WAREHOUSE_MISMATCH') {
                        // Cart belongs to Old Warehouse -> User moved to New Warehouse
                        if (confirm(resData.message || "Your location has changed. Clear cart to proceed?")) {
                             window.location.reload(); 
                        }
                        return Promise.reject(new Error("Cart conflict - Location Changed"));
                    }
                }

                // [Existing Logic] Handle 401 Unauthorized (Token Refresh Flow)
                if (response.status === 401 && !isRetry) {
                    if (ApiService.isRefreshing) {
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
                        ApiService.handleAuthFailure();
                        return;
                    }
                }

                // Parse Response
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
                        if (data.detail) errorMsg = data.detail;
                        else if (data.error) errorMsg = typeof data.error === 'object' ? JSON.stringify(data.error) : data.error;
                        else if (data.non_field_errors) errorMsg = data.non_field_errors[0];
                    }
                    throw { status: response.status, message: errorMsg, data: data };
                }

                return data === null ? {} : data;

            } catch (error) {
                if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                    console.error(`API Error [${method} ${endpoint}]:`, error);
                }
                throw error;
            }
        },

        refreshToken: async function () {
            const refreshKey = window.APP_CONFIG?.STORAGE_KEYS?.REFRESH || 'refresh_token';
            const refresh = localStorage.getItem(refreshKey);
            if (!refresh) return false;

            const baseUrl = window.APP_CONFIG?.API_BASE_URL || '/api/v1';

            try {
                const response = await fetch(`${baseUrl}/auth/refresh/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh })
                });

                if (response.ok) {
                    const data = await response.json();
                    localStorage.setItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token', data.access);
                    if (data.refresh) {
                        localStorage.setItem(refreshKey, data.refresh);
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

        handleAuthFailure: function() {
            localStorage.removeItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token');
            localStorage.removeItem(window.APP_CONFIG?.STORAGE_KEYS?.REFRESH || 'refresh_token');
            localStorage.removeItem(window.APP_CONFIG?.STORAGE_KEYS?.USER || 'user_info');

            const currentPath = window.location.pathname;
            const privatePages = [
                '/profile.html', '/orders.html', '/checkout.html',
                '/addresses.html', '/order_detail.html', '/track_order.html'
            ];

            const isPrivate = privatePages.some(page => currentPath.includes(page));

            if (isPrivate) {
                window.location.href = window.APP_CONFIG?.ROUTES?.LOGIN || '/frontend/auth.html';
            } else {
                if (!sessionStorage.getItem('auth_reload_lock')) {
                    sessionStorage.setItem('auth_reload_lock', 'true');
                    window.location.reload();
                } else {
                    setTimeout(() => sessionStorage.removeItem('auth_reload_lock'), 10000);
                }
            }
        },

        get: function (endpoint, params = {}) { 
            const queryString = new URLSearchParams(params).toString();
            const url = queryString ? `${endpoint}?${queryString}` : endpoint;
            return this.request(url, 'GET'); 
        },
        post: function (endpoint, body) { return this.request(endpoint, 'POST', body); },
        put: function (endpoint, body) { return this.request(endpoint, 'PUT', body); },
        patch: function (endpoint, body) { return this.request(endpoint, 'PATCH', body); },
        delete: function (endpoint) { return this.request(endpoint, 'DELETE'); }
    };

    window.ApiService = ApiService;
})();