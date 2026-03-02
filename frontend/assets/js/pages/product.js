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
            // 🔥 FIX: Backend se aane wala dynamic ETA use karein
            // Agar backend se ETA nahi aata toh fallback '15-25 mins' dikhayega
            const eta = p.delivery_eta || '15-25 mins';
            
            // Icon change karein delivery type ke hisaab se (Optional enhancement)
            const icon = p.delivery_type === 'dark_store' ? 'fa-bolt text-warning' : 'fa-truck text-primary';

            etaArea.innerHTML = `<i class="fas ${icon}"></i> Get it in <strong>${eta}</strong>`;
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

async function loadRelatedProducts(mainProduct) {
    try {
        const endpoint = `/catalog/skus/?limit=10`;
        const response = await window.ApiService.get(endpoint);
        let allProducts = response.results ? response.results : response;

        if (!Array.isArray(allProducts)) return;

        let filteredProducts = allProducts.filter(p => p.sku !== mainProduct.sku && p.id !== mainProduct.id);
        const productsToShow = filteredProducts.slice(0, 6); 

        const section = document.getElementById('related-products-section');
        const grid = document.getElementById('related-products-grid');

        if (productsToShow.length > 0 && section && grid) {
            section.classList.remove('d-none');
            
            grid.innerHTML = productsToShow.map(p => {
                const imageSrc = p.image_url || p.image || 'https://via.placeholder.com/150?text=No+Image';
                const finalPrice = p.sale_price || p.price || 0;
                const isOOS = p.available_stock <= 0;
                
                let discountBadge = '';
                if (p.mrp && p.sale_price && p.mrp > p.sale_price) {
                    const off = Math.round(((p.mrp - p.sale_price) / p.mrp) * 100);
                    discountBadge = `<div class="badge-off" style="position:absolute; top:8px; left:8px; background:#ef4444; color:white; padding:2px 6px; border-radius:4px; font-size:0.7rem; font-weight:bold; z-index:2;">${off}% OFF</div>`;
                }

                let deliveryBadge = '';
                if (p.delivery_eta) {
                    let badgeClass = p.delivery_type === 'dark_store' ? 'badge-instant' : 'badge-mega';
                    deliveryBadge = `<div class="${badgeClass}" style="position:absolute; top:8px; right:8px; color:white; padding:3px 6px; border-radius:6px; font-size:0.65rem; font-weight:bold; z-index:2; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">${p.delivery_eta}</div>`; 
                }

                return `
                <div class="card product-card">
                    ${discountBadge}
                    ${deliveryBadge}
                    <a href="./product.html?code=${p.sku}" style="text-decoration:none; color:inherit;">
                        <img src="${imageSrc}" style="opacity: ${isOOS ? 0.5 : 1};" loading="lazy">
                        <div class="item-name">${p.name}</div>
                        <div class="item-unit text-muted small mb-2" style="font-size:0.8rem;">${p.unit || '1 Unit'}</div>
                    </a>
                    
                    <div class="d-flex justify-between align-center mt-auto w-100">
                        <div class="price-section d-flex flex-column">
                            <span class="font-bold" style="font-size:1.05rem; line-height:1;">${Formatters.currency(finalPrice)}</span>
                            ${p.mrp > finalPrice ? `<span class="text-muted small" style="text-decoration: line-through; font-size:0.75rem; margin-top:2px;">${Formatters.currency(p.mrp)}</span>` : ''}
                        </div>
                        ${isOOS ? 
                            `<button class="btn btn-sm btn-secondary" style="border-radius:6px; padding: 6px 16px;" disabled>OOS</button>` : 
                            `<button class="btn btn-sm btn-outline-primary" style="border-radius:6px; padding: 6px 16px;" onclick="addSuggestionToCart('${p.sku}', this)">ADD</button>`
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