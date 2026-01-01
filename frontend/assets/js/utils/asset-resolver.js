(function(){
    'use strict';

    function getBase() {
        const baseEl = document.querySelector('base');
        if (baseEl && baseEl.href) return baseEl.href;
        if (window.APP_CONFIG && window.APP_CONFIG.STATIC_BASE) return window.APP_CONFIG.STATIC_BASE;
        // Fallback to current document directory
        const href = window.location.href;
        return href.replace(/#.*$/, '').replace(/\?.*$/, '').replace(/\/[^\/]*$/, '/');
    }

    function url(path) {
        if (!path) return '';
        // If path is absolute (protocol or //) return as-is
        if (/^https?:\/\//i.test(path) || /^\/\//.test(path)) return path;
        // Remove leading slash to avoid double slashes when using base
        const p = path.replace(/^\//, '');
        try {
            return new URL(p, getBase()).href;
        } catch (e) {
            return p;
        }
    }

    window.Asset = { url, base: getBase };
})();
