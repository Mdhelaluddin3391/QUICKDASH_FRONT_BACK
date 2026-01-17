// frontend/assets/js/pages/home.js

let feedPage = 1;
let feedLoading = false;
let feedHasNext = true;
let currentAbortController = null; // To cancel pending requests on location change

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Initial Load
    await initHome();

    // 2. Reactive Listener: Auto-reload when user changes location
    // Matches the event name from LocationManager.js
    const evtName = 'app:location-changed';
    window.addEventListener(evtName, async () => {
        console.log("[Home] Location changed, refreshing storefront...");
        // Reset Feed State
        feedPage = 1;
        feedHasNext = true;
        feedLoading = false;
        
        await initHome();
    });
    
    startFlashTimer();
});

async function initHome() {
    // Parallel load for independent components
    loadBanners();
    loadBrands();
    loadFlashSales();

    // 3. Location-Aware Storefront Loading
    if (window.LocationManager && window.LocationManager.hasLocation()) {
        const ctx = window.LocationManager.getLocationContext();
        
        // Use Headers Context (L1 or L2)
        if (ctx.lat && ctx.lng) {
            await loadStorefront(ctx.lat, ctx.lng, ctx.city);
        } else {
            // Location exists but no coords? Fallback.
            await loadCategories(); 
            setupInfiniteScroll();
        }
    } else {
        // No Location Set -> Show Generic Feed or Prompt
        console.warn("[Home] No location set. Loading generic categories.");
        
        // Prompt User
        document.getElementById('feed-container').innerHTML = `
            <div class="alert alert-info text-center m-3">
                <i class="fas fa-map-marker-alt"></i> 
                Please select your location to see products available in your area.
                <br>
                <button class="btn btn-sm btn-primary mt-2" onclick="window.LocationPicker.open('SERVICE')">Select Location</button>
            </div>
        `;
        
        await loadCategories();
    }
}

// 1. Optimized Storefront (Location Aware)
// 1. Optimized Storefront (Location Aware) - Updated Logic
async function loadStorefront(lat, lng, city) {
    const feedContainer = document.getElementById('feed-container');
    const catContainer = document.getElementById('category-grid');
    
    // UI Loading State
    feedContainer.innerHTML = `
        <div class="loader-spinner"></div>
        <p class="text-center text-muted small">Finding nearby store...</p>
    `;

    try {
        // Cancel previous request if any (debounce effect)
        if (currentAbortController) currentAbortController.abort();
        currentAbortController = new AbortController();

        // ApiService automatically injects X-Location headers. 
        const res = await ApiService.get(
            `/catalog/storefront/?lat=${lat}&lon=${lng}&city=${city || ''}`
        );
        
        currentAbortController = null;

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
            // UPDATED: Clear karne ki bajaye generic categories load karein taaki section dikhe
            if (catContainer) await loadCategories(); 
            return;
        }

        // Render Categories
        if (res.categories && res.categories.length > 0) {
            if (catContainer) {
                catContainer.innerHTML = res.categories.slice(0, 8).map(c => `
                    <div class="cat-card" onclick="window.location.href='./search_results.html?slug=${c.slug}'">
                        <div class="cat-img-box">
                            <img src="${c.icon || 'https://cdn-icons-png.flaticon.com/512/3703/3703377.png'}" alt="${c.name}" onerror="this.src='https://cdn-icons-png.flaticon.com/512/3703/3703377.png'">
                        </div>
                        <div class="cat-name">${c.name}</div>
                    </div>
                `).join('');
            }

            // Render Feed Sections
            feedContainer.innerHTML = res.categories.map(cat => {
                if (!cat.products || cat.products.length === 0) return '';
                return `
                <section class="feed-section">
                    <div class="section-head" style="padding: 0 20px;">
                        <h3>${cat.name}</h3>
                        <a href="./search_results.html?slug=${cat.slug}">See All</a>
                    </div>
                    <div class="product-scroll-wrapper">
                        ${cat.products.map(p => createProductCard(p)).join('')}
                    </div>
                </section>
            `}).join('');
        } else {
            // UPDATED: Agar Storefront se categories nahi aayi, toh Generic Categories load karein
            console.warn("Storefront returned no categories, loading generic fallback.");
            if (catContainer) await loadCategories();
            
            feedContainer.innerHTML = '<p class="text-center py-5">No products available in this store right now.</p>';
        }

    } catch (e) {
        if (e.name === 'AbortError') return; // Ignore cancelled requests
        console.error("Storefront failed", e);
        
        // Fallback to generic feed if Storefront crashes
        loadGenericFeed();
        // UPDATED: Error aane par bhi Categories load honi chahiye
        if (catContainer) loadCategories(); 
    }
}

function setupInfiniteScroll() {
    // Only use infinite scroll for Generic Feed (No location set)
    loadGenericFeed();
    
    // Check if sentinel already exists
    let sentinel = document.getElementById('feed-sentinel');
    if (!sentinel) {
        sentinel = document.createElement('div');
        sentinel.id = 'feed-sentinel';
        sentinel.style.height = "50px";
        sentinel.style.marginBottom = "50px";
        sentinel.innerHTML = '<div class="loader-spinner d-none"></div>'; 
        document.getElementById('feed-container').after(sentinel);

        const observer = new IntersectionObserver((entries) => {
            if(entries[0].isIntersecting && !feedLoading && feedHasNext) {
                feedPage++;
                loadGenericFeed(); 
            }
        }, { rootMargin: '200px' });

        observer.observe(sentinel);
    }
}

// 2. Generic Fallback (No Location)
async function loadGenericFeed() {
    if (feedLoading || !feedHasNext) return;
    feedLoading = true;
    const container = document.getElementById('feed-container');
    const sentinelLoader = document.querySelector('#feed-sentinel .loader-spinner');
    
    if(feedPage > 1 && sentinelLoader) sentinelLoader.classList.remove('d-none');
    if(feedPage === 1 && !container.innerHTML) container.innerHTML = '<div class="loader-spinner"></div>';

    try {
        const res = await ApiService.get(`/catalog/home/feed/?page=${feedPage}`);
        const sections = res.sections || [];
        feedHasNext = res.has_next;

        if(feedPage === 1) container.innerHTML = '';
        if (sections.length === 0 && feedPage === 1) {
            container.innerHTML = `<p class="text-center text-muted py-5">No products found!</p>`;
            return;
        }

        const html = sections.map(sec => `
            <section class="feed-section">
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
        if(feedPage === 1) container.innerHTML = `<p class="text-center text-muted py-5">Unable to load products.</p>`;
    } finally {
        feedLoading = false;
        if(sentinelLoader) sentinelLoader.classList.add('d-none');
        if(!feedHasNext) {
            const s = document.getElementById('feed-sentinel');
            if(s) s.remove();
        }
    }
}

// 3. Components
async function loadBanners() {
    const container = document.getElementById('hero-slider');
    if (!container) return;
    try {
        const banners = await ApiService.get('/catalog/banners/');
        if (banners.length > 0) {
            container.classList.remove('skeleton');
            container.innerHTML = banners.map(b => `
                <img src="${b.image_url}" class="hero-slide" 
                     onclick="window.location.href='${b.target_url || '#'}'"
                     alt="${b.title || 'Banner'}">
            `).join('');
        } else { container.style.display = 'none'; }
    } catch (e) { container.style.display = 'none'; }
}

async function loadCategories() {
    const container = document.getElementById('category-grid');
    if (!container) return;
    try {
        // Fallback for categories if Storefront API fails or no location
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
        const brands = await ApiService.get('/catalog/brands/');
        if(!brands.length) { container.style.display = 'none'; return; }
        container.innerHTML = brands.map(b => `
            <div class="brand-circle" onclick="window.location.href='./search_results.html?brand=${b.id}'">
                <img src="${b.logo_url}" alt="${b.name}">
            </div>
        `).join('');
    } catch (e) {}
}

async function loadFlashSales() {
    const section = document.getElementById('flash-sale-section');
    const grid = document.getElementById('flash-sale-grid');
    if (!section || !grid) return;
    
    try {
        const sales = await ApiService.get('/catalog/flash-sales/');
        if (!sales || sales.length === 0) {
            section.style.display = 'none';
            return;
        }
        section.style.display = 'block';
        grid.innerHTML = sales.map(item => `
            <div class="flash-card">
                <div class="badge-off">${item.discount_percent}% OFF</div>
                <a href="./product.html?code=${item.sku_id || item.sku}">
                    <img src="${item.sku_image}" style="width:100%; height:100px; object-fit:contain; margin-bottom:5px;">
                    <div style="font-size:0.85rem; font-weight:600; height:36px; overflow:hidden;">${item.sku_name}</div>
                </a>
                <div class="f-price-box">
                    <span>${Formatters.currency(item.discounted_price)}</span>
                    <span class="f-mrp">${Formatters.currency(item.original_price)}</span>
                </div>
                <button onclick="addToCart('${item.sku}', this)" class="btn btn-sm btn-primary w-100 mt-2">ADD</button>
            </div>
        `).join('');
    } catch (e) { section.style.display = 'none'; }
}

function createProductCard(p) {
    const imageSrc = p.image_url || p.image || 'https://via.placeholder.com/150?text=No+Image';
    // Handle varying price fields from different APIs (feed vs storefront)
    const price = p.sale_price || p.selling_price || p.price || 0;
    const sku = p.sku || p.id;
    
    const isOOS = p.available_stock <= 0;

    return `
        <div class="card product-card" style="padding:10px; border:1px solid #eee; box-shadow:none; position:relative;">
            <a href="./product.html?code=${sku}">
                <img src="${imageSrc}" style="width:100%; height:120px; object-fit:contain; margin-bottom:8px; opacity: ${isOOS ? 0.5 : 1}">
                <div style="font-size:0.9rem; font-weight:600; height:40px; overflow:hidden; margin-bottom:5px;">
                    ${p.name}
                </div>
            </a>
            <div class="d-flex justify-between align-center mt-2">
                <div style="font-weight:700;">${Formatters.currency(price)}</div>
                ${isOOS ? 
                    '<button class="btn btn-sm btn-secondary" disabled>OOS</button>' : 
                    `<button class="btn btn-sm btn-outline-primary" onclick="addToCart('${sku}', this)">ADD</button>`
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