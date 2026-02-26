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
        // ApiService injects X-Location headers.
        // Backend uses this to return STOCK & PRICE for THIS WAREHOUSE.
        // Endpoint supports lookup by ID or SKU.
        const product = await window.ApiService.get(`/catalog/products/${skuCode}/`);
        currentProduct = product;

        renderProduct(product);

        // NEW CODE: Load related products in the background
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
    // 'sale_price' or 'price' should come from backend logic (Warehouse specific)
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
    const etaArea = document.getElementById('eta-display'); // Ensure this element exists in HTML or handle check

    // Check 'available_stock' injected by backend
    const stock = p.available_stock !== undefined ? p.available_stock : 0;

    if (stock > 0) {
        // Enable Add Button
        const addBtn = document.getElementById('add-btn');
        if(addBtn) {
            addBtn.disabled = false;
            addBtn.innerText = "ADD TO CART";
            addBtn.onclick = addToCart;
        }
        
        // Show ETA
        if (etaArea) {
            const locType = window.LocationManager?.getLocationContext()?.type;
            const eta = locType === 'L2' ? '10-15 mins' : '15-25 mins';
            etaArea.innerHTML = `<i class="fas fa-bolt text-warning"></i> Get it in <strong>${eta}</strong>`;
            etaArea.classList.remove('text-muted');
        }
    } else {
        // Out of Stock UI
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
        // Use Singleton CartService
        // Pass SKU (string) and Quantity
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

// NEW CODE: Function to load and render recommended products
async function loadRelatedProducts(mainProduct) {
    try {
        // Yahan humne products/ ki jagah skus/ kar diya hai
        const endpoint = `/catalog/skus/?limit=10`;
        const response = await window.ApiService.get(endpoint);
        
        // Handle pagination object if your API uses it (e.g. Django REST Framework)
        let allProducts = response.results ? response.results : response;

        if (!Array.isArray(allProducts)) return;

        // Make sure we don't show the exact same product that user is currently viewing
        let filteredProducts = allProducts.filter(p => p.sku !== mainProduct.sku && p.id !== mainProduct.id);
        
        // Take top 5 items for display
        const productsToShow = filteredProducts.slice(0, 5);

        const section = document.getElementById('related-products-section');
        const grid = document.getElementById('related-products-grid');

        if (productsToShow.length > 0 && section && grid) {
            section.classList.remove('d-none'); // Unhide the container
            
            // Build and inject HTML for cards
            grid.innerHTML = productsToShow.map(p => {
                const finalPrice = p.sale_price || p.selling_price || p.price;
                const imageSrc = p.image || p.image_url || 'https://via.placeholder.com/200';
                
                // Make sure window.Formatters works safely
                const formattedPrice = window.Formatters ? window.Formatters.currency(finalPrice) : '₹' + finalPrice;
                
                return `
                    <div class="related-card border rounded p-3 d-flex flex-column align-items-center" style="background:#fff; transition: transform 0.2s;">
                        <img src="${imageSrc}" alt="${p.name}" style="width: 100%; height: 140px; object-fit: contain; cursor: pointer;" onclick="window.location.href='./product.html?code=${p.sku || p.id}'">
                        <div class="mt-3 w-100 text-left">
                            <div class="text-muted small mb-1">${p.unit || ''}</div>
                            <h6 class="text-truncate mb-2" style="font-size: 1rem; cursor: pointer;" onclick="window.location.href='./product.html?code=${p.sku || p.id}'" title="${p.name}">${p.name}</h6>
                            <div class="d-flex justify-content-between align-items-center">
                                <strong>${formattedPrice}</strong>
                                ${p.available_stock > 0 ? 
                                    `<button class="btn btn-sm btn-outline-primary" style="padding: 2px 10px;" onclick="window.location.href='./product.html?code=${p.sku || p.id}'">View</button>` 
                                    : 
                                    `<span class="badge bg-secondary text-white" style="font-size:0.7rem;">Out of Stock</span>`
                                }
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (error) {
        console.warn("Silent Fail: Related products could not be loaded", error);
    }
}



async function loadRelatedProducts(mainProduct) {
    try {
        const endpoint = `/catalog/skus/?limit=10`;
        const response = await window.ApiService.get(endpoint);
        let allProducts = response.results ? response.results : response;

        if (!Array.isArray(allProducts)) return;

        let filteredProducts = allProducts.filter(p => p.sku !== mainProduct.sku && p.id !== mainProduct.id);
        const productsToShow = filteredProducts.slice(0, 5); // 5 items

        const section = document.getElementById('related-products-section');
        const grid = document.getElementById('related-products-grid');

        if (productsToShow.length > 0 && section && grid) {
            section.classList.remove('d-none');
            
            // Render Standardized Cards
            grid.innerHTML = productsToShow.map(p => {
                const finalPrice = p.sale_price || p.selling_price || p.price;
                const imageSrc = p.image || p.image_url || 'https://via.placeholder.com/200';
                const formattedPrice = window.Formatters ? window.Formatters.currency(finalPrice) : '₹' + finalPrice;
                const isOOS = p.available_stock <= 0;

                // Standardized Delivery Badge
                let deliveryBadge = '';
                if (p.delivery_eta) {
                    let badgeClass = p.delivery_type === 'dark_store' ? 'badge-instant' : 'badge-mega';
                    let icon = p.delivery_type === 'dark_store' ? '⚡' : '📦';
                    deliveryBadge = `<div class="${badgeClass}" style="position:absolute; top:8px; right:8px; color:white; padding:3px 6px; border-radius:6px; font-size:0.65rem; font-weight:bold; z-index:2; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">${icon} ${p.delivery_eta}</div>`;
                }

                return `
                    <div class="card product-card">
                        ${deliveryBadge}
                        <a href="./product.html?code=${p.sku || p.id}" style="text-decoration:none; color:inherit;">
                            <img src="${imageSrc}" style="opacity: ${isOOS ? 0.5 : 1};">
                            <div class="item-name">${p.name}</div>
                            <div class="item-unit text-muted small mb-2" style="font-size:0.8rem;">${p.unit || '1 Unit'}</div>
                        </a>
                        <div class="d-flex justify-between align-center mt-auto">
                            <div style="font-weight:700; font-size:1.05rem;">${formattedPrice}</div>
                            ${isOOS ? 
                                `<button class="btn btn-sm btn-secondary" style="border-radius:6px; padding: 6px 16px;" disabled>OOS</button>` : 
                                `<button class="btn btn-sm btn-outline-primary" style="border-radius:6px; padding: 6px 16px;" onclick="addSuggestionToCart('${p.sku || p.id}', this)">ADD</button>`
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

// Global Suggestion Add to Cart logic specially for Product page
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
        window.Toast.success("Added");
        btn.innerHTML = '✔';
    } catch (e) {
        window.Toast.error(e.message || "Failed");
        btn.innerHTML = originalText;
    } finally {
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = "ADD";
        }, 2000);
    }
};