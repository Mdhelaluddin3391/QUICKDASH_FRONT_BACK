// frontend/assets/js/layout/main-layout.js

(function () {
    "use strict";

    const STORAGE_KEYS = window.APP_CONFIG?.STORAGE_KEYS || {};
    const EVENTS = window.APP_CONFIG?.EVENTS || {};


    function isLoggedIn() {
        const tokenKey = (window.APP_CONFIG?.STORAGE_KEYS?.TOKEN) || 'auth_token';
        return !!localStorage.getItem(tokenKey);
    }

    /**
     * Component Loader: HTML Partials (Nav/Footer)
     */
    async function loadComponent(placeholderId, filePath) {
        const element = document.getElementById(placeholderId);
        if (!element) return;

        try {
            let resolvedPath = filePath;
            if (window.Asset && typeof window.Asset.url === 'function') {
                resolvedPath = window.Asset.url(filePath);
            } else {
                if (!/^(https?:)?\/\//.test(filePath) && !filePath.startsWith('/')) {
                    resolvedPath = new URL(filePath, window.location.href).href;
                }
            }

            const response = await fetch(resolvedPath);
            if (!response.ok) throw new Error(`Failed to load ${resolvedPath}`);
            const html = await response.text();
            element.innerHTML = html;

            highlightActiveLink(element);
        } catch (error) {
            console.error(`Error loading component ${filePath}:`, error);
        }
    }

    function highlightActiveLink(container) {
        const currentPath = window.location.pathname;
        const links = container.querySelectorAll('a.nav-item, a.icon-link');
        links.forEach(link => {
            const href = link.getAttribute('href');
            if (!href) return;
            let linkPath = href;
            try {
                linkPath = new URL(href, window.location.href).pathname;
            } catch (e) { }

            if (
                linkPath === currentPath ||
                (currentPath === '/' && (linkPath === '/index.html' || linkPath === 'index.html')) ||
                (currentPath.endsWith('/') && (linkPath === 'index.html' || linkPath === '/index.html'))
            ) {
                link.classList.add('active');
                const icon = link.querySelector('i');
                if (icon) icon.style.color = 'var(--primary)';
            }
        });
    }

    function renderNavbarLocation() {
        const el = document.getElementById("header-location");
        const box = document.getElementById("navbar-location-box");
        if (!el || !box) return;

        if (!window.LocationManager) return;
        const display = window.LocationManager.getDisplayLocation();

        box.classList.remove("active-delivery", "active-service");

        el.innerHTML = `
            <div class="d-flex flex-column" style="line-height:1.2; text-align:left;">
                <span style="font-weight:600; font-size:0.95rem;">${display.label}</span>
                ${display.subtext ? `<span class="text-muted small" style="font-size:0.75rem; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${display.subtext}</span>` : ''}
            </div>
        `;

        const icon = box.querySelector('i.fas.fa-map-marker-alt') || box.querySelector('i.fas.fa-map-pin');

        if (display.type === 'DELIVERY') {
            box.classList.add("active-delivery");
            if (icon) icon.className = 'fas fa-map-marker-alt text-primary';
        } else if (display.type === 'SERVICE') {
            box.classList.add("active-service");
            if (icon) icon.className = 'fas fa-map-pin text-danger';
        } else {
            if (icon) icon.className = 'fas fa-search-location text-muted';
        }
    }

    function bindNavbarLocationClick() {
        if (document.body.dataset.navLocBound === "1") return;
        document.body.dataset.navLocBound = "1";

        document.addEventListener('click', async (e) => {
            let node = e.target;
            if (node && node.nodeType !== 1) node = node.parentElement;

            const box = (node && typeof node.closest === 'function') ? node.closest('#navbar-location-box') : null;
            if (!box) return;

            // Prevent double opening
            if (document.querySelector('.address-switcher-modal')) return;
            const modal = document.getElementById('loc-picker-modal');
            if (modal && modal.classList.contains('active')) return;

            // 1. Check if Logged In
            if (isLoggedIn()) {
                // User -> Show Address Switcher
                await openAddressSwitcher();
            } else {
                // Guest -> Open Map Picker
                openMapPickerFallback();
            }
        }, false);
    }

    async function openAddressSwitcher() {
        try {
            if (!window.ApiService) {
                console.error("ApiService not found");
                openMapPickerFallback();
                return;
            }

            const res = await window.ApiService.get('/customers/addresses/');
            const addresses = Array.isArray(res) ? res : (res.results || []);
            createAndShowAddressModal(addresses);

        } catch (err) {
            console.error("Failed to fetch addresses:", err);
            openMapPickerFallback();
        }
    }

    function createAndShowAddressModal(addresses) {
        const existing = document.querySelector('.address-switcher-modal');
        if (existing) existing.remove();

        const backdrop = document.createElement('div');
        backdrop.className = 'address-switcher-backdrop';

        const modal = document.createElement('div');
        modal.className = 'address-switcher-modal';

        let listHtml = '';
        if (addresses.length === 0) {
            listHtml = `<div class="empty-addr">No saved addresses found.</div>`;
        } else {
            listHtml = addresses.map(addr => `
                <div class="addr-item" data-json='${JSON.stringify(addr).replace(/'/g, "&#39;")}'>
                    <div class="icon"><i class="fas fa-home"></i></div>
                    <div class="details">
                        <div class="label">${addr.label || 'Address'}</div>
                        <div class="text">${addr.address_line || addr.google_address_text || ''}</div>
                    </div>
                    <div class="action"><i class="fas fa-check-circle"></i></div>
                </div>
            `).join('');
        }

        modal.innerHTML = `
            <div class="addr-header">
                <h3>Select Location</h3>
                <button class="close-btn">&times;</button>
            </div>
            <div class="addr-list">
                ${listHtml}
            </div>
            <div class="addr-footer">
                <button class="btn-gps"><i class="fas fa-crosshairs"></i> Use Current Location</button>
                <button class="btn-add"><i class="fas fa-plus"></i> Add New Address</button>
            </div>
        `;

        document.body.appendChild(backdrop);
        document.body.appendChild(modal);

        const close = () => { backdrop.remove(); modal.remove(); };
        backdrop.onclick = close;
        modal.querySelector('.close-btn').onclick = close;

        modal.querySelectorAll('.addr-item').forEach(item => {
            item.onclick = () => {
                try {
                    const data = JSON.parse(item.getAttribute('data-json'));
                    if (window.LocationManager) {
                        window.LocationManager.setDeliveryAddress(data);
                        window.location.reload();
                    }
                } catch (e) { console.error(e); }
                close();
            };
        });

        modal.querySelector('.btn-gps').onclick = () => {
            close();
            openMapPickerFallback();
        };

        modal.querySelector('.btn-add').onclick = () => {
            window.location.href = 'addresses.html';
        };
    }

    function openMapPickerFallback() {
        if (window.LocationPicker && typeof window.LocationPicker.open === 'function') {
            try { window.LocationPicker.open('SERVICE'); } catch (err) { }
            return;
        }
        try {
            const scriptId = 'loc-picker-script';
            if (!document.getElementById(scriptId)) {
                const s = document.createElement('script');
                s.id = scriptId;
                s.async = true;
                s.src = (window.Asset && typeof window.Asset.url === 'function') ? window.Asset.url('assets/js/utils/location_picker.js') : '/assets/js/utils/location_picker.js';
                s.onload = () => {
                    if (window.LocationPicker && typeof window.LocationPicker.open === 'function') {
                        try { window.LocationPicker.open('SERVICE'); } catch (err) { }
                    }
                };
                document.body.appendChild(s);
            }
        } catch (err) { }
    }

    function initializeGlobalEvents() {
        window.addEventListener(EVENTS.LOCATION_CHANGED, renderNavbarLocation);
        renderNavbarLocation();
        bindNavbarLocationClick();

        if (window.CartService && typeof window.CartService.updateGlobalCount === 'function') {
            window.CartService.updateGlobalCount();
        }
    }

    document.addEventListener("DOMContentLoaded", async () => {
        if (window.AppConfigService) {
            await window.AppConfigService.load();
        }

        await Promise.all([
            loadComponent("navbar-placeholder", "./components/navbar.html"),
            loadComponent("footer-placeholder", "./components/footer.html")
        ]);

        initializeGlobalEvents();
        fetchAndRenderNav();
    });

    async function fetchAndRenderNav() {
        const navEl = document.getElementById('dynamic-navbar');
        if (!navEl) return;

        const API_URL = `${window.APP_CONFIG.API_BASE_URL}/catalog/categories/parents/`;
        const CACHE_KEY = 'nav_parents_cache';
        const CACHE_TTL = 60 * 60 * 1000;

        try {
            const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
            const now = Date.now();
            if (cached && (now - cached.ts) < CACHE_TTL && Array.isArray(cached.data)) {
                renderNav(cached.data);
                return;
            }
        } catch (e) { }

        try {
            const resp = await fetch(API_URL);
            let data = [];
            const contentType = resp.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                data = await resp.json();
            } else {
                throw new Error("API returned non-JSON response");
            }

            if (Array.isArray(data)) {
                try {
                    localStorage.setItem(
                        CACHE_KEY,
                        JSON.stringify({ ts: Date.now(), data: data })
                    );
                } catch (e) { }

                renderNav(data);
            }
        } catch (err) {
            console.warn('Failed to fetch navbar categories:', err);
        }
    }

    function renderNav(categories) {
        const navEl = document.getElementById('dynamic-navbar');
        if (!navEl) return;

        const items = [];
        items.push(
            `<a href="index.html" class="nav-item">
                    <i class="fas fa-fire"></i> Trending
                 </a>`
        );

        categories.forEach(c => {
            const slug = c.slug || (c.name || '').toLowerCase().replace(/\s+/g, '-');
            const name = escapeHtml(c.name || 'Category');
            let imgHtml = '';
            if (c.icon_url) {
                imgHtml = `
                        <img
                            src="${escapeHtml(c.icon_url)}"
                            alt="${name}"
                            style="width:18px;height:18px;object-fit:cover;
                                   border-radius:4px;margin-right:8px;
                                   vertical-align:middle;"
                        >
                    `;
            }
            items.push(
                `<a href="search_results.html?slug=${encodeURIComponent(slug)}"
                        class="nav-item" title="${name}">
                        ${imgHtml}${name}
                    </a>`
            );
        });

        navEl.innerHTML = items.join('');
        highlightActiveLink(navEl);
    }

    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, function (m) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
        });
    }

    window.logout = async function () {
        try {
            if (window.ApiService && typeof window.ApiService.post === 'function') {
                try { await window.ApiService.post('/auth/logout/', {}); } catch (e) { }
            }
        } catch (e) { } finally {
            try {
                localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.TOKEN);
                localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.REFRESH);
                localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.USER);
            } catch (e) { }

            const privatePages = [
                '/profile.html', '/orders.html', '/checkout.html',
                '/addresses.html', '/order_detail.html', '/track_order.html'
            ];
            const currentPath = window.location.pathname;
            const isPrivate = privatePages.some(page => currentPath.includes(page));

            if (isPrivate) {
                window.location.href = APP_CONFIG.ROUTES.LOGIN;
            } else {
                try { window.location.reload(); } catch (e) { window.location.href = APP_CONFIG.ROUTES.HOME; }
            }
        }
    };

})();