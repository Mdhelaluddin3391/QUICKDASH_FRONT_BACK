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