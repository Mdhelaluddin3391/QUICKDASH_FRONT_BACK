// frontend/assets/js/pages/product.js

let currentProduct = null;
let quantity = 1;

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code') || params.get('id');

    if (!code) {
        window.location.href = './search_results.html';
        return;
    }

    await loadProduct(code);
    
    // Reactive: If user changes location in Navbar, reload stock/price info
    const evtName = (window.APP_CONFIG?.EVENTS?.LOCATION_CHANGED) || 'locationChanged';
    window.addEventListener(evtName, () => {
        console.log("Product Page: Location changed, reloading...");
        loadProduct(code);
    });
});

async function loadProduct(skuCode) {
    const loader = document.getElementById('loader');
    const content = document.getElementById('product-content');
    
    // Reset State
    quantity = 1;
    if(document.getElementById('qty-val')) document.getElementById('qty-val').innerText = "1";

    try {
        const product = await window.ApiService.get(`/catalog/products/${skuCode}/`);
        currentProduct = product;

        renderProduct(product);

        // Load related products in the background
        loadRelatedProducts(product);

        // Show
        loader.classList.add('d-none');
        content.classList.remove('d-none');

    } catch (e) {
        console.error("Product Load Error", e);
        loader.className = 'w-100 py-5'; 
        loader.innerHTML = `
            <div class="text-center">
                <p class="text-danger mb-3">Product details could not be loaded.</p>
                <p class="text-muted small">It might not be available in your selected location.</p>
                <a href="/" class="btn btn-sm btn-outline-primary">Go Home</a>
            </div>`;
    }
}

function renderProduct(p) {
    // Images
    const imgEl = document.getElementById('p-image') || document.getElementById('main-img');
    if (imgEl) imgEl.src = p.image || p.image_url || 'https://via.placeholder.com/400';
    
    // Info
    document.getElementById('p-brand').innerText = p.brand_name || 'QuickDash';
    document.getElementById('p-name').innerText = p.name;
    document.getElementById('p-unit').innerText = p.unit || '';
    document.getElementById('p-desc').innerText = p.description || "Fresh and high quality product delivered to your doorstep.";
    
    // Price Rendering
    const finalPrice = p.sale_price || p.selling_price || p.price;
    document.getElementById('p-price').innerText = window.Formatters.currency(finalPrice);
    
    if (p.mrp && p.mrp > finalPrice) {
        document.getElementById('p-mrp').innerText = window.Formatters.currency(p.mrp);
        const discount = Math.round(((p.mrp - finalPrice) / p.mrp) * 100);
        document.getElementById('p-discount').innerText = `${discount}% OFF`;
    } else {
        document.getElementById('p-mrp').innerText = '';
        document.getElementById('p-discount').innerText = '';
    }

    // Stock & ETA Logic
    const actionArea = document.getElementById('action-area');
    const etaArea = document.getElementById('eta-display'); 

    const stock = p.available_stock !== undefined ? p.available_stock : 0;

    if (stock > 0) {
        const addBtn = document.getElementById('add-btn');
        if(addBtn) {
            addBtn.disabled = false;
            addBtn.innerText = "ADD TO CART";
            addBtn.onclick = addToCart;
        }
        
        if (etaArea) {
            const locType = window.LocationManager?.getLocationContext()?.type;
            const eta = locType === 'L2' ? '10-15 mins' : '15-25 mins';
            etaArea.innerHTML = `<i class="fas fa-bolt text-warning"></i> Get it in <strong>${eta}</strong>`;
            etaArea.classList.remove('text-muted');
        }
    } else {
        const addBtn = document.getElementById('add-btn');
        if(addBtn) {
            addBtn.disabled = true;
            addBtn.innerText = "OUT OF STOCK";
            addBtn.classList.remove('btn-primary');
            addBtn.classList.add('btn-secondary');
        }
        if (etaArea) {
            etaArea.innerText = "Currently unavailable in this area.";
            etaArea.classList.add('text-muted');
        }
    }
}

window.updateQty = function(change) {
    let newQty = quantity + change;
    if (newQty < 1) newQty = 1;
    if (newQty > 10) {
        if(window.Toast) window.Toast.info("Max limit is 10 units");
        newQty = 10;
    }
    quantity = newQty;
    const qtyVal = document.getElementById('qty-val');
    if(qtyVal) qtyVal.innerText = quantity;
}

async function addToCart() {
    if (!localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = window.APP_CONFIG.ROUTES.LOGIN;
        return;
    }

    const btn = document.getElementById('add-btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerText = "Adding...";

    try {
        await window.CartService.addItem(currentProduct.sku, quantity);
        
        if(window.Toast) window.Toast.success("Added to Cart Successfully");
        
        btn.innerText = "Done";
        setTimeout(() => {
            btn.innerText = "ADD TO CART";
            btn.disabled = false; 
        }, 1500);

    } catch (e) {
        if(window.Toast) window.Toast.error(e.message || "Failed to add to cart");
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Single clean function for Related Products (Synced with APK version)
async function loadRelatedProducts(mainProduct) {
    try {
        const endpoint = `/catalog/skus/?limit=10`;
        const response = await window.ApiService.get(endpoint);
        let allProducts = response.results ? response.results : response;

        if (!Array.isArray(allProducts)) return;

        let filteredProducts = allProducts.filter(p => p.sku !== mainProduct.sku && p.id !== mainProduct.id);
        const productsToShow = filteredProducts.slice(0, 5); // Show 5 items

        const section = document.getElementById('related-products-section');
        const grid = document.getElementById('related-products-grid');

        if (productsToShow.length > 0 && section && grid) {
            section.classList.remove('d-none');
            
            // Yahan par hum container ko recommended-grid class assign kar rahe hain
            grid.className = 'recommended-grid'; 
            
            // Standardized Cards with new "recommended-card" class
            grid.innerHTML = productsToShow.map(p => {
                const finalPrice = p.sale_price || p.selling_price || p.price;
                const imageSrc = p.image || p.image_url || 'https://via.placeholder.com/200';
                const formattedPrice = window.Formatters ? window.Formatters.currency(finalPrice) : '₹' + finalPrice;
                const isOOS = p.available_stock <= 0;

                let deliveryBadge = '';
                if (p.delivery_eta) {
                    let badgeClass = p.delivery_type === 'dark_store' ? 'badge-instant' : 'badge-mega';
                    deliveryBadge = `<div class="${badgeClass}" style="position:absolute; top:8px; right:8px; color:white; padding:3px 6px; border-radius:6px; font-size:0.65rem; font-weight:bold; z-index:2; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">${p.delivery_eta}</div>`; 
                }

                return `
                    <div class="recommended-card" style="position: relative;"> ${deliveryBadge}
                        <a href="./product.html?code=${p.sku || p.id}" style="text-decoration:none; color:inherit; display:flex; flex-direction:column; align-items:center;">
                            <img src="${imageSrc}" style="width: 100%; max-width: 120px; height: 120px; object-fit: contain; margin-bottom:10px; opacity: ${isOOS ? 0.5 : 1};">
                            <div class="item-name" style="font-weight: 600; font-size: 0.85rem; line-height: 1.2; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${p.name}</div>
                            <div class="item-unit text-muted small mt-1 mb-2" style="font-size:0.75rem;">${p.unit || '1 Unit'}</div>
                        </a>
                        <div class="d-flex justify-content-between align-items-center mt-auto w-100 px-1">
                            <div style="font-weight:700; font-size:0.95rem;">${formattedPrice}</div>
                            ${isOOS ? 
                                `<button class="btn btn-sm btn-secondary" style="border-radius:6px; padding: 4px 12px; font-size: 0.8rem;" disabled>OOS</button>` : 
                                `<button class="btn btn-sm btn-outline-primary" style="border-radius:6px; padding: 4px 12px; font-size: 0.8rem; font-weight: 600;" onclick="addSuggestionToCart('${p.sku || p.id}', this)">ADD</button>`
                            }
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (error) {
        console.warn("Silent Fail: Related products could not be loaded", error);
    }
}

// Ensure global Add to cart function works on the web version as well
window.addSuggestionToCart = async function(skuCode, btn) {
    if (!localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.Toast.warning("Login required");
        setTimeout(() => window.location.href = window.APP_CONFIG.ROUTES.LOGIN, 1500);
        return;
    }
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '...';
    try {
        await window.CartService.addItem(skuCode, 1);
        if(window.Toast) window.Toast.success("Added");
        btn.innerHTML = '✔';
    } catch (e) {
        if(window.Toast) window.Toast.error(e.message || "Failed");
        btn.innerHTML = originalText;
    } finally {
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = "ADD";
        }, 2000);
    }
};