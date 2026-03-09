/**
 * Centralized API Service (Production Hardened)
 */
(function () {
    const ApiService = {
        
        isRefreshing: false,
        refreshSubscribers: [],

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

            const token = localStorage.getItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token');
            if (token && token !== 'null' && token !== 'undefined') {
                headers['Authorization'] = `Bearer ${token}`;
            }

            if (['POST', 'PUT', 'PATCH'].includes(method.toUpperCase())) {
                headers['Idempotency-Key'] = ApiService.uuidv4();
            }

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
            // 🔥 YAHAN FIX KIYA HAI: URL se Double Slash (//) Hatane ka logic
            let baseUrl = window.APP_CONFIG?.API_BASE_URL || '/api/v1';
            if (baseUrl.endsWith('/')) {
                baseUrl = baseUrl.slice(0, -1); // Remove trailing slash from base
            }
            const safeEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
            const url = `${baseUrl}${safeEndpoint}`;

            // Development testing log
            console.log(`[ApiService] ${method} Request URL:`, url);

            const options = {
                method,
                headers: ApiService.getHeaders(false, method),
            };

            if (body) {
                options.body = JSON.stringify(body);
            }

            try {
                const response = await fetch(url, options);

                if (response.status === 409) {
                    const resData = await response.clone().json().catch(() => ({}));
                    if (resData.code === 'WAREHOUSE_MISMATCH') {
                        if (confirm(resData.message || "Your location has changed. Clear cart to proceed?")) {
                             window.location.reload(); 
                        }
                        return Promise.reject(new Error("Cart conflict - Location Changed"));
                    }
                }

                if (response.status === 401 && !isRetry) {
                    if (ApiService.isRefreshing) {
                        return new Promise((resolve, reject) => {
                            ApiService.refreshSubscribers.push((wasRefreshed) => {
                                if (wasRefreshed) {
                                    resolve(ApiService.request(endpoint, method, body, true));
                                } else {
                                    reject({ status: 401, message: "Session expired" });
                                }
                            });
                        });
                    }

                    ApiService.isRefreshing = true;
                    const success = await ApiService.refreshToken();
                    ApiService.isRefreshing = false;

                    if (success) {
                        ApiService.onRefreshed(true); 
                        return ApiService.request(endpoint, method, body, true);
                    } else {
                        ApiService.onRefreshed(false); 
                        ApiService.handleAuthFailure();
                        throw { status: 401, message: "Session expired" };
                    }
                }

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
                console.error(`API Error [${method} ${url}]:`, error);
                throw error;
            }
        },

        onRefreshed: function (success) {
            ApiService.refreshSubscribers.forEach((callback) => callback(success));
            ApiService.refreshSubscribers = [];
        },

        refreshToken: async function () {
            const refreshKey = window.APP_CONFIG?.STORAGE_KEYS?.REFRESH || 'refresh_token';
            const refresh = localStorage.getItem(refreshKey);
            if (!refresh) return false;

            let baseUrl = window.APP_CONFIG?.API_BASE_URL || '/api/v1';
            if (baseUrl.endsWith('/')) baseUrl = baseUrl.slice(0, -1);

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

        handleAuthFailure: function() {
            localStorage.removeItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token');
            localStorage.removeItem(window.APP_CONFIG?.STORAGE_KEYS?.REFRESH || 'refresh_token');
            localStorage.removeItem(window.APP_CONFIG?.STORAGE_KEYS?.USER || 'user_info');
            
            this.clearCache();

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

        get: async function (endpoint, params = {}, skipCache = false) { 
            const queryString = new URLSearchParams(params).toString();
            const url = queryString ? `${endpoint}?${queryString}` : endpoint;

            const noCacheEndpoints = ['/auth/', '/cart/', '/orders/', '/checkout/', '/profile/'];
            const shouldSkipCache = skipCache || noCacheEndpoints.some(route => url.includes(route));

            const cacheKey = `api_get_cache_${url}`;

            if (!shouldSkipCache) {
                const cachedData = sessionStorage.getItem(cacheKey);
                if (cachedData) {
                    try {
                        return JSON.parse(cachedData);
                    } catch(e) { /* ignore parse error */ }
                }
            }

            const data = await this.request(url, 'GET'); 

            if (!shouldSkipCache && data) {
                try {
                    sessionStorage.setItem(cacheKey, JSON.stringify(data));
                } catch(e) { }
            }

            return data;
        },

        clearCache: function () {
            const keysToRemove = [];
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (key && (key.startsWith('api_get_cache_') || key.startsWith('cache_') || key.startsWith('storefront_'))) {
                    keysToRemove.push(key);
                }
            }
            keysToRemove.forEach(key => sessionStorage.removeItem(key));
            console.log("[ApiService] System Cache Cleared Successfully.");
        },

        post: function (endpoint, body) { return this.request(endpoint, 'POST', body); },
        put: function (endpoint, body) { return this.request(endpoint, 'PUT', body); },
        patch: function (endpoint, body) { return this.request(endpoint, 'PATCH', body); },
        delete: function (endpoint) { return this.request(endpoint, 'DELETE'); }
    };

    window.ApiService = ApiService;
})();