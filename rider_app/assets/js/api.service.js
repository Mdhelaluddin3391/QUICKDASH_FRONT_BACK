// rider_app/assets/js/api.service.js
(function () {
    const ApiService = {
        getHeaders: function () {
            const headers = { 'Content-Type': 'application/json' };
            const token = localStorage.getItem(window.RIDER_CONFIG.STORAGE_KEYS.TOKEN);
            if (token) headers['Authorization'] = `Bearer ${token}`;
            return headers;
        },

        request: async function (endpoint, method = 'GET', body = null) {
            const url = `${window.RIDER_CONFIG.API_BASE_URL}${endpoint}`;
            const options = { method, headers: this.getHeaders() };
            if (body) options.body = JSON.stringify(body);

            try {
                const response = await fetch(url, options);
                
                // 401 Unauthorized handle (Auto Logout)
                if (response.status === 401) {
                    localStorage.clear();
                    window.location.href = window.RIDER_CONFIG.ROUTES.LOGIN;
                    return;
                }

                const data = await response.json();
                if (!response.ok) throw { message: data.detail || data.error || "Error" };
                return data;
            } catch (error) {
                console.error("API Error:", error);
                throw error;
            }
        },

        get: function (url) { return this.request(url, 'GET'); },
        post: function (url, body) { return this.request(url, 'POST', body); }
    };
    window.ApiService = ApiService;
})();