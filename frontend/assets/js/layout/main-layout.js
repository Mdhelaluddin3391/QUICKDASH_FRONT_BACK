// frontend/assets/js/layout/main-layout.js

(function () {
    "use strict";

    const STORAGE_KEYS = window.APP_CONFIG?.STORAGE_KEYS || {};
    const EVENTS = window.APP_CONFIG?.EVENTS || {};

    function isLoggedIn() {
        // ✅ FIX 3A: 'auth_token' को हटाकर 'access_token' करें
        const tokenKey = (window.APP_CONFIG?.STORAGE_KEYS?.TOKEN) || 'access_token';
        return !!localStorage.getItem(tokenKey);
    }

    /**
     * Component Loader: HTML Partials (Nav/Footer)
     * 🔥 ADDED: HTML Caching to prevent re-fetching and blinking
     */
    async function loadComponent(placeholderId, filePath) {
        const element = document.getElementById(placeholderId);
        if (!element) return;

        // --- 🔥 HTML CACHE LOGIC START ---
        const cacheKey = `html_cache_${filePath}`;
        const cachedHtml = sessionStorage.getItem(cacheKey);

        if (cachedHtml) {
            element.innerHTML = cachedHtml;
            highlightActiveLink(element);
            return; // Cache mil gaya, aage fetch karne ki zaroorat nahi
        }
        // --- HTML CACHE LOGIC END ---

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
            
            // Save fetched HTML to SessionStorage
            try { sessionStorage.setItem(cacheKey, html); } catch(e) {}

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

        // 👉 YAHAN UPDATE KIYA GAYA HAI: SVG icon select aur set karne ka code
        const icon = box.querySelector('.modern-location-icon');

        if (display.type === 'DELIVERY') {
            box.classList.add("active-delivery");
            if (icon) icon.setAttribute('class', 'modern-location-icon text-primary');
        } else if (display.type === 'SERVICE') {
            box.classList.add("active-service");
            if (icon) icon.setAttribute('class', 'modern-location-icon text-danger');
        } else {
            if (icon) icon.setAttribute('class', 'modern-location-icon text-muted');
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

        // ✅ FIX 3B: डुप्लीकेट Cart API कॉल को हटा दिया गया है
        const tokenKey = (window.APP_CONFIG?.STORAGE_KEYS?.TOKEN) || 'access_token';
        if (!localStorage.getItem(tokenKey)) {
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
        // 🔥 CACHE KEY UPDATED TO '_v2' taaki browser automatically naya data fetch kare
        const CACHE_KEY = 'nav_parents_cache_v2'; 
        
        const cachedStr = localStorage.getItem(CACHE_KEY);
        if (cachedStr) {
            try {
                const cached = JSON.parse(cachedStr);
                if (cached && (Date.now() - cached.ts) < 3600000 && Array.isArray(cached.data)) {
                    renderNav(cached.data);
                    return; 
                }
            } catch (e) {
                console.warn("Nav Cache invalid, fetching fresh data...");
            }
        }

        try {
            const resp = await fetch(API_URL);
            if (!resp.ok) throw new Error(`API failed with status: ${resp.status}`);
            const data = await resp.json();
            
            if (Array.isArray(data)) {
                localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: data }));
                renderNav(data);
            }
        } catch (err) { 
            console.error("Failed to load nav categories:", err);
        }
    }

    function renderNav(categories) {
        const navEl = document.getElementById('dynamic-navbar');
        if (!navEl) return;

        // Current page ka slug nikalte hain
        const currentUrl = new URL(window.location.href);
        const currentSlug = currentUrl.searchParams.get('slug');

        const items = [];
        items.push(`<a href="index.html" class="nav-item"><i class="fas fa-fire"></i> Trending</a>`);

        const seenNames = new Set();
        let activeCategory = null; // Yahan save karenge jiska child nav dikhana hai

        // --- 1. Main Navbar Render ---
        categories.forEach(c => {
            const name = c.name || 'Category';
            if (seenNames.has(name)) return; 
            seenNames.add(name);

            const slug = c.slug || name.toLowerCase().replace(/\s+/g, '-');
            
            // Check karein kya ye category active hai ya iska koi sub-category active hai
            if (currentSlug === slug) {
                activeCategory = c;
            } else if (c.subcategories && c.subcategories.some(sub => sub.slug === currentSlug)) {
                activeCategory = c;
            }

            let imgHtml = c.icon_url ? `<img src="${c.icon_url}" alt="${name}" style="width:18px;height:18px;object-fit:cover;border-radius:4px;margin-right:8px;vertical-align:middle;">` : '';
            
            items.push(`<a href="search_results.html?slug=${encodeURIComponent(slug)}" class="nav-item" title="${name}">${imgHtml}${name}</a>`);
        });

        navEl.innerHTML = items.join('');
        highlightActiveLink(navEl);

        // --- 2. Sub-Navbar Render (Scrollable Row below Main Nav) ---
        let subNavEl = document.getElementById('dynamic-subnavbar');
        if (!subNavEl) {
            // Agar nahi hai toh naya div banayenge theek navEl ke niche
            subNavEl = document.createElement('div');
            subNavEl.id = 'dynamic-subnavbar';
            // Same 'header-nav-row' class lagayenge taaki automatically horizontal scroll aa jaye
            subNavEl.className = 'header-nav-row'; 
            subNavEl.style.backgroundColor = '#f8f9fa';
            subNavEl.style.borderTop = '1px solid #eaeaea';
            subNavEl.style.padding = '8px 15px';
            subNavEl.style.gap = '10px';
            
            navEl.parentNode.insertBefore(subNavEl, navEl.nextSibling);
        }

        // Agar humein active parent category mil gayi jiske andar sub-categories hain
        if (activeCategory && activeCategory.subcategories && activeCategory.subcategories.length > 0) {
            
            // "All" ka ek button banate hain
            const subItems = [
                `<a href="search_results.html?slug=${encodeURIComponent(activeCategory.slug)}" class="nav-item" style="font-size:0.85rem; padding:5px 12px; background:#fff; border:1px solid #ddd; border-radius:20px; white-space:nowrap;">All ${activeCategory.name}</a>`
            ];

            // Subcategories ko pill-style mein add karte hain
            activeCategory.subcategories.forEach(sub => {
                subItems.push(`<a href="search_results.html?slug=${encodeURIComponent(sub.slug)}" class="nav-item" style="font-size:0.85rem; padding:5px 12px; background:#fff; border:1px solid #ddd; border-radius:20px; white-space:nowrap;">${sub.name}</a>`);
            });

            subNavEl.innerHTML = subItems.join('');
            subNavEl.style.display = 'flex'; // Dikhayenge
            highlightActiveLink(subNavEl);   // Isme bhi active link highlight hoga
        } else {
            subNavEl.style.display = 'none'; // Chupayenge agar zaroorat nahi
        }
    }

    window.logout = async function () {
        try {
            if (window.ApiService?.post) await window.ApiService.post('/auth/logout/', {});
        } catch (e) { } finally {
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.TOKEN);
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.REFRESH);
            
            // --- 🔥 Cache clearing applied here already by you ---
            if (window.ApiService) { window.ApiService.clearCache(); } else { sessionStorage.clear(); }

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

// frontend/assets/js/layout/main-layout.js ke end me update karein
document.addEventListener('DOMContentLoaded', async () => {
    await checkStoreStatus();
});

async function checkStoreStatus() {
    // 🔥 FIX: Faltu API Calls Rokne Ke Liye 5 Minute Ka Cache Lagaya Hai
    const CACHE_KEY = 'store_status_cache';
    const cachedStr = sessionStorage.getItem(CACHE_KEY);
    
    if (cachedStr) {
        try {
            const cached = JSON.parse(cachedStr);
            // Agar cache 5 minute (300000 ms) se purana nahi hai, toh wahi use karein
            if (Date.now() - cached.ts < 300000) { 
                if (cached.data.is_store_open === false) {
                    showStoreOfflineUI(cached.data.store_closed_message);
                }
                return; // Yahan se return ho jayega, API call nahi hogi
            }
        } catch (e) {
            console.warn("Store status cache invalid");
        }
    }

    try {
        const baseUrl = window.APP_CONFIG?.API_BASE_URL || 'https://quickdash-front-back.onrender.com/api/v1';
        const response = await fetch(`${baseUrl}/core/store-status/`);
        
        if (response.ok) {
            const data = await response.json();
            
            // Naya data aane par Cache mein save karein
            sessionStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: data }));
            
            if (data.is_store_open === false) {
                showStoreOfflineUI(data.store_closed_message);
            }
        } else {
            console.error("Store status API returned:", response.status);
        }
    } catch (error) {
        console.error("Error fetching store status:", error);
    }
}

function showStoreOfflineUI(message) {
    document.body.classList.add('store-closed-mode');
    const overlay = document.createElement('div');
    overlay.className = 'store-offline-overlay';
    const modal = document.createElement('div');
    modal.className = 'store-offline-modal';
    
    modal.innerHTML = `
        <h2>Store is Offline</h2>
        <p>${message}</p>
    `;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}