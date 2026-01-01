// frontend/assets/js/layout/main-layout.js

(function () {
    "use strict";

    const STORAGE_KEYS = window.APP_CONFIG?.STORAGE_KEYS || {};
    const EVENTS = window.APP_CONFIG?.EVENTS || {};

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
            } catch (e) {}

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
            if(icon) icon.className = 'fas fa-map-marker-alt text-primary';
        } else if (display.type === 'SERVICE') {
            box.classList.add("active-service");
            if(icon) icon.className = 'fas fa-map-pin text-danger';
        } else {
            if(icon) icon.className = 'fas fa-search-location text-muted';
        }
    }

    function bindNavbarLocationClick() {
        if (document.body.dataset.navLocBound === "1") return;
        document.body.dataset.navLocBound = "1";

        document.addEventListener('click', (e) => {
            let node = e.target;
            if (node && node.nodeType !== 1) node = node.parentElement;

            const box = (node && typeof node.closest === 'function') ? node.closest('#navbar-location-box') : null;
            if (!box) return;

            const modal = document.getElementById('loc-picker-modal');
            if (modal && modal.classList.contains('active')) return;

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
            } catch (err) {}
        }, false);
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

        // [FIXED] Fetch ONLY Parent Categories for Navbar
        async function fetchAndRenderNav() {
            const navEl = document.getElementById('dynamic-navbar');
            if (!navEl) return;

            // Updated Endpoint: /categories/parents/
            const API_URL = `${window.APP_CONFIG.API_BASE_URL}/catalog/categories/parents/`;
            const CACHE_KEY = 'nav_parents_cache';
            const CACHE_TTL = 60 * 60 * 1000; // 1 hour

            // 1. Try Local Storage Cache
            try {
                const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
                const now = Date.now();
                if (cached && (now - cached.ts) < CACHE_TTL && Array.isArray(cached.data)) {
                    renderNav(cached.data);
                    return;
                }
            } catch (e) { }

            // 2. Fetch Live Data
            try {
                const resp = await fetch(API_URL);
                
                // Safe JSON parsing to prevent "Error: 0: <"
                let data = [];
                const contentType = resp.headers.get("content-type");
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    data = await resp.json();
                } else {
                    throw new Error("API returned non-JSON response");
                }

                if (Array.isArray(data)) {
                    // Update Cache
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

        fetchAndRenderNav();
    });

    window.logout = async function() {
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