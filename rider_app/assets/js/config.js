// rider_app/assets/js/config.js
(function() {
    // Backend API URL (Apne server IP se replace karein agar mobile main chala rahe hain)
    const apiBase = "https://quickdash-front-back.onrender.com/api/v1";

    window.RIDER_CONFIG = {
        API_BASE_URL: apiBase,
        STORAGE_KEYS: {
            TOKEN: 'rider_access_token',
            REFRESH: 'rider_refresh_token',
            USER: 'rider_user_data'
        },
        ROUTES: {
            LOGIN: 'index.html',
            DASHBOARD: 'dashboard.html'
        }
    };
})();