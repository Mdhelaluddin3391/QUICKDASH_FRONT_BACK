// ✅ Delivery Fee Variable add kiya gaya hai
const DELIVERY_FEE = 5.00;

document.addEventListener('DOMContentLoaded', async () => {
    // Auth Check
    if (!localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = APP_CONFIG.ROUTES.LOGIN;
        return;
    }

    await loadCart();
});

async function loadCart() {
    const loader = document.getElementById('loader');
    const empty = document.getElementById('empty-cart');
    const content = document.getElementById('cart-content');
    const list = document.getElementById('cart-items');

    try {
        const cart = await CartService.getCart();

        loader.classList.add('d-none');

        if (!cart.items || cart.items.length === 0) {
            empty.classList.remove('d-none');
            content.classList.add('d-none');
            return;
        }

        content.classList.remove('d-none');
        document.getElementById('item-count').innerText = `${cart.items.length} Items`;

        // Render Items
        list.innerHTML = cart.items.map(item => {
            // यहाँ quantity को Number में बदलें ताकि जोड़-घटाव सही हो
            const currentQty = parseInt(item.quantity);

            // FIX: Use item.sku_code and item.image to match the backend API response
            return `
    <div class="card cart-item" id="item-card-${item.sku_code}">
        <img src="${item.image || 'https://via.placeholder.com/80'}" class="item-img">
        <div class="item-details">
            <div class="item-name">${item.sku_name}</div>
            <div class="item-unit text-muted small">${item.sku_unit || ''}</div>
            <div class="item-price">${Formatters.currency(item.total_price)}</div>
        </div>
        <div class="qty-and-delete">
            <div class="qty-control">
                <button class="qty-btn-sm" onclick="changeQty('${item.sku_code}', ${currentQty - 1})">
                    <i class="fas fa-minus"></i>
                </button>
                <span id="qty-${item.sku_code}" class="mx-2">${currentQty}</span>
                <button class="qty-btn-sm" onclick="changeQty('${item.sku_code}', ${currentQty + 1})">
                    <i class="fas fa-plus"></i>
                </button>
            </div>
            <button class="btn btn-outline btn-sm delete-btn ms-3" onclick="deleteItem('${item.sku_code}')">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    </div>
`}).join('');

        // ✅ Sirf 'Total (To Pay)' Update karein
        const subtotal = parseFloat(cart.total_amount || 0);
        const total = subtotal + DELIVERY_FEE;

        // Subtotal aur Delivery ki extra lines hata di hain, taaki error na aaye
        document.getElementById('total').innerText = Formatters.currency(total);

    } catch (e) {
        console.error(e);
        loader.innerHTML = '<p class="text-danger text-center">Failed to load cart</p>';
    }
}

window.changeQty = async function (skuCode, newQty) {
    try {
        // अगर यूजर 0 कर रहा है, तो delete logic कॉल करें
        if (newQty <= 0) {
            await deleteItem(skuCode);
            return;
        }

        // UI Feedback: बटन डिसेबल करें
        const card = document.getElementById(`item-card-${skuCode}`);
        if (card) {
            const btns = card.querySelectorAll('button');
            btns.forEach(b => b.disabled = true);
            card.style.opacity = '0.7';
        }

        await CartService.updateItem(skuCode, newQty);
        await loadCart();

    } catch (e) {
        if (window.Toast) Toast.error("Failed to update cart");

        // एरर आने पर वापस इनेबल करें
        const card = document.getElementById(`item-card-${skuCode}`);
        if (card) {
            const btns = card.querySelectorAll('button');
            btns.forEach(b => b.disabled = false);
            card.style.opacity = '1';
        }
    }
};

window.deleteItem = async function (skuCode) {
    try {
        if (!confirm("Remove item from cart?")) return;

        // UI Feedback: Disable buttons temporarily
        const card = document.getElementById(`item-card-${skuCode}`);
        if (card) {
            const btns = card.querySelectorAll('button');
            btns.forEach(b => b.disabled = true);
            card.style.opacity = '0.7';
        }

        await CartService.updateItem(skuCode, 0); // Setting quantity to 0 removes the item
        await loadCart(); // Refresh UI

    } catch (e) {
        if (window.Toast) Toast.error("Failed to remove item");
        // Re-enable on error
        const card = document.getElementById(`item-card-${skuCode}`);
        if (card) {
            const btns = card.querySelectorAll('button');
            btns.forEach(b => b.disabled = false);
            card.style.opacity = '1';
        }
    }
};