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

            // Load hone ke baad highlight karein
            highlightActiveLink(element);
        } catch (error) {
            console.error(`Error loading component ${filePath}:`, error);
        }
    }

    /**
     * [UPDATED] Smart Link Highlighting
     * Ab ye Query Parameters (slug) ko bhi check karega
     */
    function highlightActiveLink(container) {
        try {
            const currentUrl = new URL(window.location.href);
            const currentPath = currentUrl.pathname; // e.g. /search_results.html
            const currentSlug = currentUrl.searchParams.get('slug'); // e.g. fruits

            // Select generic nav items and icon links
            const links = container.querySelectorAll('a.nav-item, a.icon-link, .nav-links a');
            
            links.forEach(link => {
                link.classList.remove('active'); // Reset purana active
                
                // Cleanup inline icon color if previously added
                const icon = link.querySelector('i');
                if (icon) icon.style.removeProperty('color');

                const href = link.getAttribute('href');
                if (!href) return;

                // Resolve link URL absolute path to compare safely
                const linkUrl = new URL(href, window.location.href);
                const linkPath = linkUrl.pathname;
                const linkSlug = linkUrl.searchParams.get('slug');

                let isActive = false;

                // CASE 1: Category Pages (Jahan slug matter karta hai)
                if (currentPath.includes('search_results.html') && linkPath.includes('search_results.html')) {
                    // Sirf tab active karein jab slug match kare
                    if (currentSlug && linkSlug && currentSlug === linkSlug) {
                        isActive = true;
                    }
                }
                // CASE 2: Normal Pages (Home, Orders, Profile)
                else {
                    // Simple Path Match
                    if (linkPath === currentPath) {
                        isActive = true;
                    }
                    // Root / vs index.html handle
                    else if ((currentPath === '/' && linkPath.endsWith('index.html')) || 
                             (linkPath === '/' && currentPath.endsWith('index.html'))) {
                        isActive = true;
                    }
                }

                // Apply Active Class
                if (isActive) {
                    link.classList.add('active');
                    // Agar icon hai toh color set karein (CSS fallback)
                    if (icon && link.classList.contains('icon-link')) {
                        icon.style.color = 'var(--primary)';
                    }
                }
            });
        } catch(e) { console.error("Highlight error", e); }
    }

    // ---------------------------------------------------------
    // Location Rendering Logic (L1 vs L2)
    // ---------------------------------------------------------
    function renderNavbarLocation() {
        const el = document.getElementById("header-location");
        const box = document.getElementById("navbar-location-box");
        if (!el || !box) return;

        if (!window.LocationManager) return;
        const display = window.LocationManager.getDisplayLocation();

        // Reset Classes
        box.classList.remove("active-delivery", "active-service");

        // Render Text
        el.innerHTML = `
            <div class="d-flex flex-column" style="line-height:1.2; text-align:left;">
                <span style="font-weight:600; font-size:0.95rem;">${display.label}</span>
                ${display.subtext ? `<span class="text-muted small" style="font-size:0.75rem; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${display.subtext}</span>` : ''}
            </div>
        `;

        // Render Icon / Color Status
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

            if (document.querySelector('.address-switcher-modal')) return;
            const modal = document.getElementById('loc-picker-modal');
            if (modal && modal.classList.contains('active')) return;

            if (isLoggedIn()) {
                await openAddressSwitcher();
            } else {
                openMapPickerFallback();
            }
        }, false);
    }

    async function openAddressSwitcher() {
        try {
            if (!window.ApiService) {
                openMapPickerFallback();
                return;
            }
            const res = await window.ApiService.get('/customers/addresses/');
            const addresses = Array.isArray(res) ? res : (res.results || []);
            createAndShowAddressModal(addresses);
        } catch (err) {
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
            <div class="addr-list">${listHtml}</div>
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
                } catch (e) { }
                close();
            };
        });

        modal.querySelector('.btn-gps').onclick = () => { close(); openMapPickerFallback(); };
        modal.querySelector('.btn-add').onclick = () => { window.location.href = 'addresses.html'; };
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
                    if (window.LocationPicker) window.LocationPicker.open('SERVICE');
                };
                document.body.appendChild(s);
            }
        } catch (err) { }
    }

    function checkProtectedRoutes() {
        const privatePages = ['/profile.html', '/orders.html', '/checkout.html', '/addresses.html', '/order_detail.html', '/track_order.html'];
        const currentPath = window.location.pathname;
        const isPrivate = privatePages.some(page => currentPath.includes(page));
        
        if (isPrivate && !isLoggedIn()) {
            document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;"><p>Redirecting to Login...</p></div>';
            const loginRoute = window.APP_CONFIG?.ROUTES?.LOGIN || 'auth.html';
            window.location.href = `${loginRoute}?next=${encodeURIComponent(currentPath)}`;
            throw new Error("Access Denied");
        }
    }

    function initializeGlobalEvents() {
        checkProtectedRoutes();
        if (window.EVENTS?.LOCATION_CHANGED) {
            window.addEventListener(window.EVENTS.LOCATION_CHANGED, renderNavbarLocation);
        }
        renderNavbarLocation();
        bindNavbarLocationClick();

        const tokenKey = (window.APP_CONFIG?.STORAGE_KEYS?.TOKEN) || 'auth_token';
        if (localStorage.getItem(tokenKey) && window.CartService?.updateGlobalCount) {
            window.CartService.updateGlobalCount();
        } else {
            document.querySelectorAll('.cart-count').forEach(el => el.style.display = 'none');
        }
    }

    document.addEventListener("DOMContentLoaded", async () => {
        if (window.AppConfigService) await window.AppConfigService.load();
        
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
        
        try {
            const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
            if (cached && (Date.now() - cached.ts) < 3600000 && Array.isArray(cached.data)) {
                renderNav(cached.data);
                return;
            }
        } catch (e) { }

        try {
            const resp = await fetch(API_URL);
            const data = await resp.json();
            if (Array.isArray(data)) {
                localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: data }));
                renderNav(data);
            }
        } catch (err) { }
    }

    function renderNav(categories) {
        const navEl = document.getElementById('dynamic-navbar');
        if (!navEl) return;

        const items = [];
        
        // 1. Trending Link (Static) - इसे हमेशा सबसे ऊपर रखें
        items.push(
            `<a href="index.html" class="nav-item">
                <i class="fas fa-fire"></i> Trending
             </a>`
        );

        // 2. Duplicate Check के लिए Set बनाएं (Use category name for uniqueness)
        const seenNames = new Set();

        // 3. Dynamic Categories Loop
        categories.forEach(c => {
            const name = c.name || 'Category';
            
            // अगर यह name पहले लिस्ट में आ चुका है, तो इसे छोड़ दें (Skip duplicate)
            if (seenNames.has(name)) {
                return; 
            }
            
            // अगर नया है, तो इसे Set में नोट करें
            seenNames.add(name);

            // Slug बनाएं
            const slug = c.slug || name.toLowerCase().replace(/\s+/g, '-');
            
            let imgHtml = '';
            if (c.icon_url) {
                imgHtml = `<img src="${c.icon_url}" alt="${name}" style="width:18px;height:18px;object-fit:cover;border-radius:4px;margin-right:8px;vertical-align:middle;">`;
            }
            
            // HTML लिस्ट में जोड़ें
            items.push(
                `<a href="search_results.html?slug=${encodeURIComponent(slug)}" class="nav-item" title="${name}">
                    ${imgHtml}${name}
                 </a>`
            );
        });

        // HTML अपडेट करें
        navEl.innerHTML = items.join('');
        
        // एक्टिव लिंक हाइलाइट करें
        highlightActiveLink(navEl);
    }

    window.logout = async function () {
        try {
            if (window.ApiService?.post) await window.ApiService.post('/auth/logout/', {});
        } catch (e) { } finally {
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.TOKEN);
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.REFRESH);
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.USER);
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.DELIVERY_CONTEXT);
            
            const privatePages = ['/profile.html', '/orders.html', '/checkout.html', '/addresses.html', '/order_detail.html', '/track_order.html'];
            const currentPath = window.location.pathname;
            
            if (privatePages.some(page => currentPath.includes(page))) {
                window.location.href = APP_CONFIG.ROUTES.LOGIN;
            } else {
                window.location.reload();
            }
        }
    };
})();