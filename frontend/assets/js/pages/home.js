// frontend/assets/js/pages/home.js

let feedPage = 1;
let feedLoading = false;
let feedHasNext = true;

let sfPage = 1;
let sfLoading = false;
let sfHasNext = true;
let flashTimerId = null;
let currentAbortController = null; 

document.addEventListener('DOMContentLoaded', async () => {
    await initHome();

    const evtName = 'app:location-changed';
    window.addEventListener(evtName, async () => {
        console.log("[Home] Location changed, refreshing storefront...");
        
        if (window.ApiService) {
            window.ApiService.clearCache();
        } else {
            sessionStorage.clear();
        }

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
    loadBanners();
    loadBrands();
    loadFlashSales();
    loadCategories(); 

    const feedContainer = document.getElementById('feed-container');
    feedContainer.innerHTML = '';

    if (window.LocationManager && window.LocationManager.hasLocation()) {
        const ctx = window.LocationManager.getLocationContext();
        if (ctx.lat && ctx.lng) {
            await loadStorefront(ctx.lat, ctx.lng, ctx.city, true); 
            setupStorefrontScroll(ctx.lat, ctx.lng, ctx.city);
        } else {
            setupGenericScroll();
        }
    } else {
        console.warn("[Home] No location set. Loading generic categories.");
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
    
    sfLoading = true;
    
    if (isInitial) {
        feedContainer.innerHTML = `
            <div class="loader-spinner"></div>
            <p class="text-center text-muted small">Finding nearby store...</p>
        `;
    } else {
        insertSentinelLoader(feedContainer);
    }

    try {
        if (currentAbortController) currentAbortController.abort();
        currentAbortController = new AbortController();

        const res = await ApiService.get(
            `/catalog/storefront/?lat=${lat}&lon=${lng}&city=${city || ''}&page=${sfPage}`
        );
        
        currentAbortController = null;
        removeSentinelLoader();

        if (res.serviceable === false) {
            feedContainer.innerHTML = `
                <div class="text-center py-5">
                    <img src="/assets/images/empty-store.png" style="width:120px; opacity:0.8; margin-bottom:15px;" onerror="this.style.display='none'">
                    <h4 style="color: #dc3545; font-weight: 600;">Not Serviceable Area</h4>
                    <p class="text-muted">We don't deliver to <strong>${city || 'this location'}</strong> yet.</p>
                    <button class="btn mt-2" 
                            style="background-color: #dc3545; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; box-shadow: 0 4px 6px rgba(220, 53, 69, 0.2);" 
                            onclick="window.LocationPicker.open('SERVICE')">
                        Change Location
                    </button>
                </div>
            `;
            sfHasNext = false; 
            return;
        }

        sfHasNext = res.has_next;
        if(sfHasNext) sfPage++;

        if (isInitial) feedContainer.innerHTML = '';

        if (res.categories && res.categories.length > 0) {
            // 🔥 Frontend Grouping: Agar Backend galti se subcategory bheje toh yahan handle ho jayega
            const groupedData = groupCategoriesForFeed(res.categories);
            
            const html = groupedData.map(cat => {
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
            feedContainer.innerHTML = '<p class="text-center py-5">No products available in this store right now.</p>';
        }

    } catch (e) {
        if (e.name === 'AbortError') return; 
        console.error("Storefront failed", e);
        removeSentinelLoader();
        
        if (isInitial) {
            loadGenericFeed(true); 
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

        // 🔥 Frontend Grouping apply kiya gaya hai
        const groupedData = groupCategoriesForFeed(sections, true);

        const html = groupedData.map(sec => `
            <section class="feed-section fade-in">
                <div class="section-head" style="padding: 0 20px;">
                    <h3>${sec.name || sec.category_name}</h3>
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

// 🔥 Naya Helper Function: Pagination tode bina Sub-categories ko Parent title ke under merge karta hai
function groupCategoriesForFeed(categories, isGeneric = false) {
    const groupedMap = new Map();
    const result = [];

    categories.forEach(cat => {
        // Assume API sends parent name, otherwise fallback to item category
        let titleName = cat.name || cat.category_name;
        let slug = cat.slug || titleName.toLowerCase().replace(/\s+/g, '-');
        
        if (groupedMap.has(titleName)) {
            // Agar same name ka section already iss page par hai, toh uske products add kardo
            const existingCat = groupedMap.get(titleName);
            existingCat.products = existingCat.products.concat(cat.products);
        } else {
            // Naya section banayein
            const newCat = {
                name: titleName,
                slug: slug,
                products: [...(cat.products || [])]
            };
            groupedMap.set(titleName, newCat);
            result.push(newCat);
        }
    });

    return result;
}


// =========================================================
// UTILITIES & COMPONENTS
// =========================================================

function createObserver(callback, conditionFn) {
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
    }, { rootMargin: '300px' }); 

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

async function loadBanners() {
    const heroContainer = document.getElementById('hero-slider');
    const midContainer = document.getElementById('mid-banner-container'); 
    
    if (!heroContainer) return;
    
    try {
        const response = await ApiService.get('/catalog/banners/');
        const banners = response.results ? response.results : response;

        if (banners && banners.length > 0) {
            const heroBanners = banners.filter(b => b.position === 'HERO');
            const midBanners = banners.filter(b => b.position === 'MID');

            if (heroBanners.length > 0) {
                heroContainer.classList.remove('skeleton');
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
        console.error("Banner load error:", e);
        heroContainer.style.display = 'none'; 
    }
}

async function loadCategories() {
    const container = document.getElementById('category-grid');
    if (!container) return;
    try {
        const cats = await ApiService.get('/catalog/categories/parents/');
        if (Array.isArray(cats) && cats.length > 0) {
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
        const brandsToShow = brands.slice(0, 8);

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
        const sales = response.results ? response.results : response;

        if (!Array.isArray(sales) || sales.length === 0) {
            section.style.display = 'none';
            return;
        }
        
        section.style.display = 'block';
        grid.innerHTML = sales.map(item => {
            let deliveryBadge = '';
            if (item.delivery_eta) {
                let badgeClass = item.delivery_type === 'dark_store' ? 'badge-instant' : 'badge-mega';
                deliveryBadge = `<div class="${badgeClass}" style="position:absolute; top:8px; right:8px; color:white; padding:3px 6px; border-radius:6px; font-size:0.65rem; font-weight:bold; z-index:2; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">${item.delivery_eta}</div>`;
            }

            return `
            <div class="flash-card" style="position: relative; display: flex; flex-direction: column;">
                ${deliveryBadge}
                <div class="badge-off">${item.discount_percent}% OFF</div>
                
                <a href="./product.html?code=${item.sku_id || item.sku}" style="text-decoration:none; color:inherit;">
                    <img src="${item.sku_image}" style="width:100%; height:110px; object-fit:contain; margin-bottom:10px;" onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
                    <div style="font-size:0.95rem; font-weight:600; height:40px; overflow:hidden; line-height:1.4; margin-bottom:4px;">${item.sku_name}</div>
                </a>
                
                <div class="f-price-box mt-auto d-flex justify-between align-center">
                    <div>
                        <span style="font-weight:700; font-size:1.05rem; color:#111;">${Formatters.currency(item.discounted_price)}</span>
                        <span class="f-mrp text-muted small" style="text-decoration:line-through; font-size:0.75rem;">${Formatters.currency(item.original_price)}</span>
                    </div>
                </div>
                
                <button onclick="window.addToCart('${item.sku || item.sku_id}', this)" class="btn btn-sm btn-primary w-100 mt-2" style="border-radius:6px; padding:8px;">ADD</button>
            </div>
        `}).join('');
    } catch (e) { 
        console.error("Flash Sales load error:", e);
        section.style.display = 'none'; 
    }
}

function createProductCard(p) {
    const imageSrc = p.image_url || p.image || 'https://via.placeholder.com/150?text=No+Image';
    const price = p.sale_price || p.selling_price || p.price || 0;
    const sku = p.sku || p.id;
    const isOOS = p.available_stock <= 0;
    
    let deliveryBadge = '';
    if (p.delivery_eta) {
        let badgeClass = p.delivery_type === 'dark_store' ? 'badge-instant' : 'badge-mega';
        deliveryBadge = `<div class="${badgeClass}" style="position:absolute; top:8px; right:8px; color:white; padding:3px 6px; border-radius:6px; font-size:0.65rem; font-weight:bold; z-index:2; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">${p.delivery_eta}</div>`; 
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
    
    if (flashTimerId) {
        clearInterval(flashTimerId);
    }
    
    const end = new Date();
    end.setHours(23, 59, 59, 999); 
    
    flashTimerId = setInterval(() => {
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

window.handleBannerClick = function(url) {
    if (!url || url === '#' || url === 'null') return;
    if (url.startsWith('http')) {
        try {
            const urlObj = new URL(url);
            window.location.href = urlObj.pathname + urlObj.search;
        } catch (e) {
            window.location.href = url;
        }
    } else {
        window.location.href = url;
    }
};