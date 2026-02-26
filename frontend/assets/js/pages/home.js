// frontend/assets/js/pages/home.js

// State Variables for Generic Feed
let feedPage = 1;
let feedLoading = false;
let feedHasNext = true;

// State Variables for Storefront (Location Aware) Feed
let sfPage = 1;
let sfLoading = false;
let sfHasNext = true;

let currentAbortController = null; // To cancel pending requests on location change

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Initial Load
    await initHome();

    // 2. Reactive Listener: Auto-reload when user changes location
    // Matches the event name from LocationManager.js
    const evtName = 'app:location-changed';
    window.addEventListener(evtName, async () => {
        console.log("[Home] Location changed, refreshing storefront...");
        
        // --- 🔥 SMART CACHE CLEAR ADDED HERE ---
        if (window.ApiService) {
            window.ApiService.clearCache();
        } else {
            sessionStorage.clear();
        }

        // Reset Feed States
        feedPage = 1;
        feedHasNext = true;
        feedLoading = false;
        
        sfPage = 1;
        sfHasNext = true;
        sfLoading = false;
        
        await initHome();
    });
    
    startFlashTimer();
});

async function initHome() {
    // Parallel load for independent components
    // 'loadCategories' ko yahan move kiya taaki 8 categories hamesha dikhein
    loadBanners();
    loadBrands();
    loadFlashSales();
    loadCategories(); 

    // Clear feed container before loading
    const feedContainer = document.getElementById('feed-container');
    feedContainer.innerHTML = '';

    // 3. Location-Aware Storefront Loading
    if (window.LocationManager && window.LocationManager.hasLocation()) {
        const ctx = window.LocationManager.getLocationContext();
        
        // Use Headers Context (L1 or L2)
        if (ctx.lat && ctx.lng) {
            await loadStorefront(ctx.lat, ctx.lng, ctx.city, true); // true = Initial load
            setupStorefrontScroll(ctx.lat, ctx.lng, ctx.city);
        } else {
            // Location exists but no coords? Fallback.
            setupGenericScroll();
        }
    } else {
        // No Location Set -> Show Generic Feed or Prompt
        console.warn("[Home] No location set. Loading generic categories.");
        
        // Prompt User
        feedContainer.innerHTML = `
            <div class="alert alert-info text-center m-3">
                <i class="fas fa-map-marker-alt"></i> 
                Please select your location to see products available in your area.
                <br>
                <button class="btn btn-sm btn-primary mt-2" onclick="window.LocationPicker.open('SERVICE')">Select Location</button>
            </div>
        `;
        
        setupGenericScroll();
    }
}

// =========================================================
// 1. STOREFRONT INFINITE SCROLL (Location ON)
// =========================================================

async function loadStorefront(lat, lng, city, isInitial = false) {
    if (sfLoading || !sfHasNext) return;
    
    const feedContainer = document.getElementById('feed-container');
    const catContainer = document.getElementById('category-grid');
    
    sfLoading = true;
    
    // UI Loading State
    if (isInitial) {
        feedContainer.innerHTML = `
            <div class="loader-spinner"></div>
            <p class="text-center text-muted small">Finding nearby store...</p>
        `;
    } else {
        insertSentinelLoader(feedContainer);
    }

    try {
        // Cancel previous request if any (debounce effect)
        if (currentAbortController) currentAbortController.abort();
        currentAbortController = new AbortController();

        // ApiService automatically injects X-Location headers. 
        // Pass page parameter for pagination
        const res = await ApiService.get(
            `/catalog/storefront/?lat=${lat}&lon=${lng}&city=${city || ''}&page=${sfPage}`
        );
        
        currentAbortController = null;
        removeSentinelLoader();

        // --- [CRITICAL CHECK: Serviceability] ---
        if (res.serviceable === false) {
            feedContainer.innerHTML = `
                <div class="text-center py-5">
                    <img src="/assets/images/empty-store.png" style="width:120px; opacity:0.6; margin-bottom:15px;" onerror="this.style.display='none'">
                    <h4>Not Serviceable Area</h4>
                    <p class="text-muted">We don't deliver to <strong>${city || 'this location'}</strong> yet.</p>
                    <button class="btn btn-outline-primary mt-2" onclick="window.LocationPicker.open('SERVICE')">
                        Change Location
                    </button>
                </div>
            `;
            sfHasNext = false; // Stop further loading
            return;
        }

        // Update Infinite Scroll State
        sfHasNext = res.has_next;
        if(sfHasNext) sfPage++;

        if (isInitial) feedContainer.innerHTML = '';

        // Render Categories
        if (res.categories && res.categories.length > 0) {
            
            // NOTE: Yahan se wo code hata diya jo 'catContainer' ko update karta tha.
            // Kyunki storefront API pagination ki wajah se sirf 4 categories bhej raha hai.
            // Upar wala 'Shop by Category' section ab 'loadCategories()' sambhalega jo hamesha 8 dikhayega.

            // Render Feed Sections (Append mode)
            const html = res.categories.map(cat => {
                if (!cat.products || cat.products.length === 0) return '';
                return `
                <section class="feed-section fade-in">
                    <div class="section-head" style="padding: 0 20px;">
                        <h3>${cat.name}</h3>
                        <a href="./search_results.html?slug=${cat.slug}">See All</a>
                    </div>
                    <div class="product-scroll-wrapper">
                        ${cat.products.map(p => createProductCard(p)).join('')}
                    </div>
                </section>
            `}).join('');
            
            feedContainer.insertAdjacentHTML('beforeend', html);

        } else if (isInitial) {
            console.warn("Storefront returned no categories, loading generic fallback.");
            feedContainer.innerHTML = '<p class="text-center py-5">No products available in this store right now.</p>';
        }

    } catch (e) {
        if (e.name === 'AbortError') return; // Ignore cancelled requests
        console.error("Storefront failed", e);
        removeSentinelLoader();
        
        // Fallback to generic feed if Storefront crashes on initial load
        if (isInitial) {
            loadGenericFeed(true); // true = isInitial
        }
    } finally {
        sfLoading = false;
    }
}

function setupStorefrontScroll(lat, lng, city) {
    createObserver(() => loadStorefront(lat, lng, city, false), () => sfHasNext && !sfLoading);
}

// =========================================================
// 2. GENERIC FEED INFINITE SCROLL (Location OFF)
// =========================================================

function setupGenericScroll() {
    createObserver(() => loadGenericFeed(false), () => feedHasNext && !feedLoading);
}

async function loadGenericFeed(isInitial = false) {
    if (feedLoading || !feedHasNext) return;
    
    feedLoading = true;
    const container = document.getElementById('feed-container');
    
    if(isInitial) container.innerHTML = '<div class="loader-spinner"></div>';
    else insertSentinelLoader(container);

    try {
        const res = await ApiService.get(`/catalog/home/feed/?page=${feedPage}`);
        const sections = res.sections || [];
        removeSentinelLoader();
        
        feedHasNext = res.has_next;
        if(feedHasNext) feedPage++;

        if(isInitial) container.innerHTML = '';
        if (sections.length === 0 && isInitial) {
            container.innerHTML = `<p class="text-center text-muted py-5">No products found!</p>`;
            return;
        }

        const html = sections.map(sec => `
            <section class="feed-section fade-in">
                <div class="section-head" style="padding: 0 20px;">
                    <h3>${sec.category_name}</h3>
                    <a href="./search_results.html?slug=${sec.slug}">View All</a>
                </div>
                <div class="product-scroll-wrapper">
                    ${sec.products.map(p => createProductCard(p)).join('')}
                </div>
            </section>
        `).join('');
        container.insertAdjacentHTML('beforeend', html);

    } catch (e) {
        console.error("Feed Error", e);
        removeSentinelLoader();
        if(isInitial) container.innerHTML = `<p class="text-center text-muted py-5">Unable to load products.</p>`;
    } finally {
        feedLoading = false;
    }
}

// =========================================================
// UTILITIES & COMPONENTS
// =========================================================

// Shared Intersection Observer for Infinite Scroll
function createObserver(callback, conditionFn) {
    // Remove old sentinel if exists
    const old = document.getElementById('feed-sentinel');
    if(old) old.remove();

    const sentinel = document.createElement('div');
    sentinel.id = 'feed-sentinel';
    sentinel.style.height = "20px";
    sentinel.style.marginBottom = "50px"; 
    document.getElementById('feed-container').after(sentinel);

    const observer = new IntersectionObserver((entries) => {
        if(entries[0].isIntersecting && conditionFn()) {
            callback();
        }
    }, { rootMargin: '300px' }); // Pre-load 300px before reaching bottom

    observer.observe(sentinel);
}

function insertSentinelLoader(container) {
    let loader = document.getElementById('scroll-loader');
    if(!loader) {
        loader = document.createElement('div');
        loader.id = 'scroll-loader';
        loader.className = 'text-center py-3';
        loader.innerHTML = '<div class="loader-spinner" style="width:30px;height:30px;"></div>';
        container.appendChild(loader);
    }
}

function removeSentinelLoader() {
    const loader = document.getElementById('scroll-loader');
    if(loader) loader.remove();
}

// 3. Components
async function loadBanners() {
    const heroContainer = document.getElementById('hero-slider');
    const midContainer = document.getElementById('mid-banner-container'); // Naya container HTML se
    
    if (!heroContainer) return;
    
    try {
        const response = await ApiService.get('/catalog/banners/');
        const banners = response.results ? response.results : response;

        if (banners && banners.length > 0) {
            
            // 1. HERO aur MID banners ko unki position ke hisaab se alag karein
            const heroBanners = banners.filter(b => b.position === 'HERO');
            const midBanners = banners.filter(b => b.position === 'MID');

            // 2. HERO Banners set karein (Upar wale section ke liye)
            if (heroBanners.length > 0) {
                heroContainer.classList.remove('skeleton');
                // style mein 100% width aur cover object-fit lagaya hai taaki size perfect aaye
                heroContainer.innerHTML = heroBanners.map(b => `
                    <img src="${b.image_url}" class="hero-slide" 
                         style="width: 100%; height: 100%; object-fit: cover; border-radius: 12px; max-height: 200px;"
                         onclick="handleBannerClick('${b.target_url}')"
                         alt="${b.title || 'Hero Banner'}">
                `).join('');
                heroContainer.style.display = 'block';
            } else {
                heroContainer.style.display = 'none';
            }

            // 3. MID Banners set karein (Beech wale section ke liye)
            if (midContainer && midBanners.length > 0) {
                midContainer.innerHTML = midBanners.map(b => `
                    <div class="mid-banner" onclick="handleBannerClick('${b.target_url}')">
                        <img src="${b.image_url}" alt="${b.title || 'Mid Banner'}">
                    </div>
                `).join('');
                midContainer.style.display = 'block';
            }

        } else { 
            heroContainer.style.display = 'none'; 
            if(midContainer) midContainer.style.display = 'none';
        }
    } catch (e) { 
        console.error("Banner load hone mein error:", e);
        heroContainer.style.display = 'none'; 
    }
}

async function loadCategories() {
    const container = document.getElementById('category-grid');
    if (!container) return;
    try {
        // Fallback for categories if Storefront API fails or no location
        const cats = await ApiService.get('/catalog/categories/parents/');
        if (Array.isArray(cats) && cats.length > 0) {
            // Updated: Slice(0, 8) ensures exactly 8 categories are shown
            container.innerHTML = cats.slice(0, 8).map(c => `
                <div class="cat-card" onclick="window.location.href='./search_results.html?slug=${c.slug}'">
                    <div class="cat-img-box">
                        <img src="${c.icon_url || 'https://cdn-icons-png.flaticon.com/512/3703/3703377.png'}" alt="${c.name}">
                    </div>
                    <div class="cat-name">${c.name}</div>
                </div>
            `).join('');
        }
    } catch (e) { console.warn('Category grid load failed:', e); }
}

async function loadBrands() {
    const container = document.getElementById('brand-scroller');
    if (!container) return;
    
    try {
        const response = await ApiService.get('/catalog/brands/');
        const brands = response.results ? response.results : response;

        if(!brands || brands.length === 0) { 
            container.style.display = 'none'; 
            return; 
        }

        container.style.display = 'flex';
        
        // Fix: Sirf shuru ke 8 brands hi dikhayein (.slice(0, 8) use karke)
        const brandsToShow = brands.slice(0, 8);

        // Updated Structure: Image ke niche Name show karne ke liye
        container.innerHTML = brandsToShow.map(b => `
            <div class="brand-item" onclick="window.location.href='./search_results.html?brand=${b.id}'">
                <div class="brand-circle">
                    <img src="${b.logo_url || b.logo || 'https://via.placeholder.com/100?text=Brand'}" alt="${b.name}">
                </div>
                <div class="brand-name">${b.name}</div>
            </div>
        `).join('');
    } catch (e) {
        console.error("Brands load error:", e);
        container.style.display = 'none';
    }
}

async function loadFlashSales() {
    const section = document.getElementById('flash-sale-section');
    const grid = document.getElementById('flash-sale-grid');
    if (!section || !grid) return;
    
    try {
        const response = await ApiService.get('/catalog/flash-sales/');
        
        // FIX: Paginated response ko handle karna
        const sales = response.results ? response.results : response;

        if (!Array.isArray(sales) || sales.length === 0) {
            section.style.display = 'none';
            return;
        }
        
        section.style.display = 'block';
        grid.innerHTML = sales.map(item => `
            <div class="flash-card">
                <div class="badge-off">${item.discount_percent}% OFF</div>
                <a href="./product.html?code=${item.sku_id || item.sku}">
                    <img src="${item.sku_image}" style="width:100%; height:100px; object-fit:contain; margin-bottom:5px;" onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
                    <div style="font-size:0.85rem; font-weight:600; height:36px; overflow:hidden;">${item.sku_name}</div>
                </a>
                <div class="f-price-box">
                    <span>${Formatters.currency(item.discounted_price)}</span>
                    <span class="f-mrp">${Formatters.currency(item.original_price)}</span>
                </div>
                <button onclick="addToCart('${item.sku}', this)" class="btn btn-sm btn-primary w-100 mt-2">ADD</button>
            </div>
        `).join('');
    } catch (e) { 
        // FIX: Error ko console mein dikhayein taaki debugging mein aasaani ho
        console.error("Flash Sales load error:", e);
        section.style.display = 'none'; 
    }
}

function createProductCard(p) {
    const imageSrc = p.image_url || p.image || 'https://via.placeholder.com/150?text=No+Image';
    const price = p.sale_price || p.selling_price || p.price || 0;
    const sku = p.sku || p.id;
    const isOOS = p.available_stock <= 0;
    
    // ETA / Delivery Badge logic (Standardized)
    let deliveryBadge = '';
    if (p.delivery_eta) {
        let badgeClass = p.delivery_type === 'dark_store' ? 'badge-instant' : 'badge-mega';
        let icon = p.delivery_type === 'dark_store' ? '⚡' : '📦';
        deliveryBadge = `<div class="${badgeClass}" style="position:absolute; top:8px; right:8px; color:white; padding:3px 6px; border-radius:6px; font-size:0.65rem; font-weight:bold; z-index:2; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">${icon} ${p.delivery_eta}</div>`;
    }

    return `
        <div class="card product-card">
            ${deliveryBadge}
            <a href="./product.html?code=${sku}" style="text-decoration:none; color:inherit;">
                <img src="${imageSrc}" style="opacity: ${isOOS ? 0.5 : 1}">
                <div class="item-name">${p.name}</div>
                <div class="item-unit text-muted small mb-2" style="font-size:0.8rem;">${p.unit || '1 Unit'}</div>
            </a>
            <div class="d-flex justify-between align-center mt-auto">
                <div style="font-weight:700; font-size:1.05rem;">${Formatters.currency(price)}</div>
                ${isOOS ? 
                    '<button class="btn btn-sm btn-secondary" style="border-radius:6px; padding: 6px 16px;" disabled>OOS</button>' : 
                    `<button class="btn btn-sm btn-outline-primary" style="border-radius:6px; padding: 6px 16px;" onclick="window.addToCart('${sku}', this)">ADD</button>`
                }
            </div>
        </div>
    `;
}

function startFlashTimer() {
    const display = document.getElementById('flash-timer');
    if(!display) return;
    
    // Set End time to End of Today (Demo Logic)
    const end = new Date();
    end.setHours(23, 59, 59, 999); 
    
    setInterval(() => {
        const diff = end - new Date();
        if(diff <= 0) { display.innerText = "00:00:00"; return; }
        const h = Math.floor((diff / (1000 * 60 * 60)) % 24);
        const m = Math.floor((diff / (1000 * 60)) % 60);
        const s = Math.floor((diff / 1000) % 60);
        display.innerText = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }, 1000);
}

window.addToCart = async function(skuCode, btn) {
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        Toast.warning("Login required to add items");
        setTimeout(() => window.location.href = APP_CONFIG.ROUTES.LOGIN, 1500);
        return;
    }
    
    const originalText = btn.innerText;
    btn.innerText = "..";
    btn.disabled = true;
    
    try {
        // Use standard CartService
        await CartService.addItem(skuCode, 1);
        Toast.success("Added to cart");
        btn.innerText = "✔";
        setTimeout(() => { btn.innerText = originalText; btn.disabled = false; }, 1500);
    } catch (e) {
        Toast.error(e.message || "Failed to add");
        btn.innerText = originalText;
        btn.disabled = false;
    }
};

// --- APK Navigation Fix for Banners ---
window.handleBannerClick = function(url) {
    if (!url || url === '#' || url === 'null') return;
    
    // Agar URL main http ya https hai, toh usko relative path main convert karein
    if (url.startsWith('http')) {
        try {
            const urlObj = new URL(url);
            // Sirf path aur query params nikalega (e.g., /search_results.html?slug=veg)
            window.location.href = urlObj.pathname + urlObj.search;
        } catch (e) {
            window.location.href = url;
        }
    } else {
        // Agar already relative URL hai (e.g., ./product.html)
        window.location.href = url;
    }
};