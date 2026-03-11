const CURRENT_APP_VERSION = "2.8.3";

function isUpdateAvailable(currentVersion, latestVersion) {
    const current = currentVersion.replace('v', '').split('.').map(Number);
    const latest = latestVersion.replace('v', '').split('.').map(Number);

    for (let i = 0; i < 3; i++) {
        let currPart = current[i] || 0;
        let latestPart = latest[i] || 0;

        if (latestPart > currPart) return true;
        if (latestPart < currPart) return false;
    }
    return false;
}

(function () {
    "use strict";

    const STORAGE_KEYS = window.APP_CONFIG?.STORAGE_KEYS || {};
    const EVENTS = window.APP_CONFIG?.EVENTS || {};

    function isLoggedIn() {
        const tokenKey = (window.APP_CONFIG?.STORAGE_KEYS?.TOKEN) || 'access_token';
        return !!localStorage.getItem(tokenKey);
    }

    async function loadComponent(placeholderId, filePath) {
        const element = document.getElementById(placeholderId);
        if (!element) return;

        const cacheKey = `html_cache_${filePath}`;
        const cachedHtml = sessionStorage.getItem(cacheKey);

        if (cachedHtml) {
            element.innerHTML = cachedHtml;
            highlightActiveLink(element);
            return;
        }

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
            
            try { sessionStorage.setItem(cacheKey, html); } catch(e) {}

            element.innerHTML = html;
            highlightActiveLink(element);
        } catch (error) {
            console.error(`Error loading component ${filePath}:`, error);
        }
    }

    function highlightActiveLink(container) {
        try {
            const currentUrl = new URL(window.location.href);
            const currentPath = currentUrl.pathname;
            const currentSlug = currentUrl.searchParams.get('slug');

            const links = container.querySelectorAll('a.nav-item, a.icon-link, .nav-links a');
            
            links.forEach(link => {
                link.classList.remove('active');
                
                const icon = link.querySelector('i');
                if (icon) icon.style.removeProperty('color');

                const href = link.getAttribute('href');
                if (!href) return;

                const linkUrl = new URL(href, window.location.href);
                const linkPath = linkUrl.pathname;
                const linkSlug = linkUrl.searchParams.get('slug');

                let isActive = false;

                if (currentPath.includes('search_results.html') && linkPath.includes('search_results.html')) {
                    if (currentSlug && linkSlug && currentSlug === linkSlug) {
                        isActive = true;
                    }
                } else {
                    if (linkPath === currentPath) {
                        isActive = true;
                    } else if ((currentPath === '/' && linkPath.endsWith('index.html')) || 
                             (linkPath === '/' && currentPath.endsWith('index.html'))) {
                        isActive = true;
                    }
                }

                if (isActive) {
                    link.classList.add('active');
                    if (icon && link.classList.contains('icon-link')) {
                        icon.style.color = 'var(--primary)';
                    }
                }
            });
        } catch(e) { console.error("Highlight error", e); }
    }

    // 📍 YAHAN SVG ICON KA LOGIC UPDATE KIYA GAYA HAI 📍
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

        // Select the Modern Bouncing SVG Icon
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
    // 📍 END UPDATE 📍

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
        // --- 2. Sub-Navbar Render (Scrollable Row below Main Nav) ---
        let subNavEl = document.getElementById('dynamic-subnavbar');
        if (!subNavEl) {
            // Agar nahi hai toh naya div banayenge theek navEl ke niche
            subNavEl = document.createElement('div');
            subNavEl.id = 'dynamic-subnavbar';
            subNavEl.className = 'header-nav-row'; 
            subNavEl.style.backgroundColor = '#f8f9fa';
            subNavEl.style.borderTop = '1px solid #eaeaea';
            subNavEl.style.padding = '8px 15px';
            subNavEl.style.gap = '10px';
            
            navEl.parentNode.insertBefore(subNavEl, navEl.nextSibling);
        }

        // Agar humein active parent category mil gayi jiske andar sub-categories hain
        if (activeCategory && activeCategory.subcategories && activeCategory.subcategories.length > 0) {
            
            // 🔥 Yahan se extra 'style' hata diya gaya hai, ab sirf class="nav-item" hai
            const subItems = [
                `<a href="search_results.html?slug=${encodeURIComponent(activeCategory.slug)}" class="nav-item">All ${activeCategory.name}</a>`
            ];

            // Subcategories ko add karte hain
            activeCategory.subcategories.forEach(sub => {
                subItems.push(`<a href="search_results.html?slug=${encodeURIComponent(sub.slug)}" class="nav-item">${sub.name}</a>`);
            });

            subNavEl.innerHTML = subItems.join('');
            subNavEl.style.display = 'flex'; 
            highlightActiveLink(subNavEl);   
        } else {
            subNavEl.style.display = 'none'; 
        }
    }

    window.logout = async function () {
        try {
            if (window.ApiService?.post) await window.ApiService.post('/auth/logout/', {});
        } catch (e) { } finally {
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.TOKEN);
            localStorage.removeItem(APP_CONFIG.STORAGE_KEYS.REFRESH);
            
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

document.addEventListener('DOMContentLoaded', async () => {
    await checkStoreStatus();
    await checkForAppUpdates(); 
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

document.addEventListener('DOMContentLoaded', () => {
    if (window.PullToRefresh) {
        PullToRefresh.init({
            mainElement: 'body',
            
            // Yahan hum condition laga rahe hain ki refresh kab allow karna hai
            shouldPullToRefresh: function() {
                // Un sabhi popups ya modals ki class/id check karein jo open ho sakte hain
                const activePopups = document.querySelectorAll('.address-switcher-modal, #loc-picker-modal.active, .store-offline-overlay, .update-app-overlay, .modal.active');
                
                // Agar inmein se koi bhi popup exist karta hai (ya open hai), toh refresh rok do
                if (activePopups.length > 0) {
                    return false;
                }
                
                // Agar user page ke bilkul top par hai, tabhi refresh allow karo
                return window.scrollY === 0;
            },

            onRefresh: function() {
                return new Promise((resolve) => {
                    window.location.reload(); 
                    resolve();
                });
            },
            instructionsPullToRefresh: 'Pull down to refresh',
            instructionsReleaseToRefresh: 'Release to refresh',
            instructionsRefreshing: 'Refreshing...',
        });
    }
});

async function checkForAppUpdates() {
    try {
        const versionUrl = "https://raw.githubusercontent.com/Mdhelaluddin3391/APK/main/version.json?t=" + Date.now();
        
        const response = await fetch(versionUrl);
        
        if (response.ok) {
            const data = await response.json();
            
            if (isUpdateAvailable(CURRENT_APP_VERSION, data.versionName)) {
                showUpdatePopupUI(data);
            }
        }
    } catch (error) {
        console.error("Error checking for updates:", error);
    }
}

function showUpdatePopupUI(updateData) {
    if (document.querySelector('.update-app-overlay')) return;

    document.body.classList.add('update-mode');
    document.body.style.overflow = 'hidden'; 
    
    const overlay = document.createElement('div');
    overlay.className = 'update-app-overlay';
    overlay.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:9999; display:flex; justify-content:center; align-items:center; padding:20px;';
    
    const modal = document.createElement('div');
    modal.className = 'update-app-modal';
    modal.style.cssText = 'background:#fff; width:100%; max-width:400px; padding:20px; border-radius:12px; text-align:center; box-shadow:0 4px 15px rgba(0,0,0,0.2);';
    
    const notesHtml = updateData.releaseNotes ? updateData.releaseNotes.replace(/\n/g, '<br>') : 'Performance improvements and bug fixes.';

    modal.innerHTML = `
        <h2 style="margin-top:0; color:#333;">New Update Available!</h2>
        <p style="color:#666; font-size:14px; margin-bottom:10px;">Version ${updateData.versionName} is now available.</p>
        <div style="background:#f8f9fa; padding:10px; border-radius:8px; text-align:left; font-size:13px; margin-bottom:20px; color:#555; max-height:150px; overflow-y:auto;">
            <strong>What's New:</strong><br>
            ${notesHtml}
        </div>
        
        <div id="update-progress-container" style="display:none; margin-bottom: 15px; text-align: left;">
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:5px; color:#555; font-weight: bold;">
                <span id="update-progress-text">Downloading... 0%</span>
                <span id="update-progress-bytes">0 MB / 0 MB</span>
            </div>
            <div style="width:100%; background:#e0e0e0; border-radius:6px; height:8px; overflow:hidden;">
                <div id="update-progress-bar" style="width:0%; background:var(--primary, #007bff); height:100%; transition:width 0.2s ease;"></div>
            </div>
        </div>

        <button id="download-update-btn" style="background:var(--primary, #007bff); color:#fff; border:none; padding:12px 20px; width:100%; border-radius:8px; font-size:16px; font-weight:bold; cursor:pointer;">
            Update Now
        </button>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const downloadBtn = document.getElementById('download-update-btn');
    const progressContainer = document.getElementById('update-progress-container');
    const progressBar = document.getElementById('update-progress-bar');
    const progressText = document.getElementById('update-progress-text');
    const progressBytes = document.getElementById('update-progress-bytes');
    
    downloadBtn.addEventListener('click', async () => {
        downloadBtn.innerText = "Downloading... Please wait";
        downloadBtn.disabled = true; 
        downloadBtn.style.opacity = '0.7';
        downloadBtn.style.display = 'none'; 
        progressContainer.style.display = 'block'; 

        let progressListener;

        try {
            const fileName = 'quickdash-update.apk';
            
            progressListener = await Capacitor.Plugins.Filesystem.addListener('progress', (progress) => {
                if (progress.url === updateData.apkUrl) {
                    const percent = Math.round((progress.bytes / progress.contentLength) * 100);
                    progressBar.style.width = percent + '%';
                    progressText.innerText = `Downloading... ${percent}%`;
                    
                    const downloadedMB = (progress.bytes / (1024 * 1024)).toFixed(2);
                    const totalMB = (progress.contentLength / (1024 * 1024)).toFixed(2);
                    progressBytes.innerText = `${downloadedMB} MB / ${totalMB} MB`;
                }
            });

            const downloadResult = await Capacitor.Plugins.Filesystem.downloadFile({
                url: updateData.apkUrl,
                path: fileName,
                directory: 'CACHE',
                progress: true 
            });

            if (progressListener) {
                progressListener.remove();
            }

            progressText.innerText = "Download Complete!";
            progressBar.style.width = '100%';
            downloadBtn.style.display = 'block';
            downloadBtn.innerText = "Installing...";

            const apkPath = downloadResult.path || downloadResult.uri; 

            cordova.plugins.fileOpener2.open(
                apkPath, 
                'application/vnd.android.package-archive', 
                {
                    error: function(e) { 
                        console.error('Error opening APK:', e); 
                        downloadBtn.innerText = "Install Failed. Try Again"; 
                        downloadBtn.disabled = false;
                        downloadBtn.style.opacity = '1';
                    },
                    success: function() { 
                        console.log('Install prompt opened successfully'); 
                        downloadBtn.innerText = "Installing..."; 
                    }
                }
            );
            
        } catch (err) {
            console.error("Download Error:", err);
            if (progressListener) progressListener.remove();
            progressContainer.style.display = 'none';
            downloadBtn.style.display = 'block';
            downloadBtn.innerText = "Download Failed. Try Again";
            downloadBtn.disabled = false;
            downloadBtn.style.opacity = '1';
        }
    });
}
