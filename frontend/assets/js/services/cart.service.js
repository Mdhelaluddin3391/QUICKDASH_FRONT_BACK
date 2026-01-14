// frontend/assets/js/services/cart.service.js

/**
 * CartService: Singleton for managing Cart State & API calls.
 * Production Ready: Handles Location Switching conflicts.
 */
(function () {
    const CartService = {
        _count: 0,
        _total: 0,

        init: async function() {
            if (localStorage.getItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token')) {
                await this.updateGlobalCount();
            }
            this.initListener();
        },

        getCart: async function () {
            try {
                // ApiService injects Location Headers automatically
                const res = await window.ApiService.get('/orders/cart/');
                this._total = res.total_amount || 0;
                this._count = (res.items || []).length;
                this._notifyChange(res);
                return res;
            } catch (error) {
                console.error("CartService: Get failed", error);
                throw error;
            }
        },

        addItem: async function (sku, qty = 1) {
            return this.updateItem(sku, qty);
        },

        updateItem: async function (sku, qty) {
            try {
                // Note: Warehouse ID is handled by Backend Middleware via Headers
                // We don't need to send it explicitly unless overriding
                const res = await window.ApiService.post('/orders/cart/add/', {
                    sku: sku,
                    quantity: qty
                });
                this._total = res.total_amount || 0;
                this._count = (res.items || []).length;
                this._notifyChange(res);
                return res;

            } catch (error) {
                // Handle Warehouse Mismatch (Conflict)
                // If backend returns 409 or explicit location mismatch error
                if (error.status === 409 || (error.message && error.message.includes("Location Mismatch"))) {
                    if(confirm("Your cart contains items from another store. Clear it to add this item?")) {
                         return await window.ApiService.post('/orders/cart/add/', {
                            sku: sku,
                            quantity: qty,
                            force_clear: true
                        });
                    }
                }
                throw error;
            }
        },

        clearCart: async function () {
            try {
                await window.ApiService.delete('/orders/cart/');
                this._count = 0;
                this._total = 0;
                this._notifyChange({ items: [], total_amount: 0 });
            } catch (e) {
                console.error("Cart clear failed", e);
            }
        },

        updateGlobalCount: async function () {
            try {
                const res = await window.ApiService.get('/orders/cart/');
                this._count = (res.items || []).length;
                this._updateBadges();
            } catch (e) { 
                this._updateBadges(); 
            }
        },

        _updateBadges: function() {
            const badges = document.querySelectorAll('.cart-count');
            badges.forEach(el => {
                el.innerText = this._count;
                el.style.display = this._count > 0 ? 'flex' : 'none';
            });
        },

        _notifyChange: function (cartData) {
            this._updateBadges();
            window.dispatchEvent(new CustomEvent('cartUpdated', { detail: cartData }));
        },

        initListener() {
            // Listen for Location Changes to re-validate cart if needed
            // Updated to match LocationManager event
            window.addEventListener('app:location-changed', async () => {
                await this.validateCartOnLocationChange();
            });
        },

        async validateCartOnLocationChange() {
            const token = localStorage.getItem(window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token');
            if (!token) return; 

            // ApiService will send new location headers automatically
            try {
                // This call will fail with 409 if middleware detects warehouse mismatch
                const res = await window.ApiService.post('/orders/validate-cart/', {});
                
                if (res.is_valid === false) {
                    this.showConflictModal(res.unavailable_items || []);
                }
            } catch (e) {
                // Warning is expected if cart is empty or valid
            }
        },

        showConflictModal(items) {
            const itemName = items.length > 0 ? items[0].product_name : "Items";
            const msg = items.length > 0 
                ? `${itemName} and others are not available at this new location.`
                : "Your cart items are from a different store.";
                
            if (confirm(`⚠️ Location Changed\n\n${msg}\n\nDo you want to clear your cart to shop here?`)) {
                // Force clear logic
                window.ApiService.post('/orders/cart/add/', { force_clear: true, sku: 'DUMMY', quantity: 0 })
                    .then(() => {
                        this.updateGlobalCount();
                        if (window.Toast) window.Toast.info("Cart cleared for new location.");
                        if (window.location.pathname.includes('cart.html')) window.location.reload();
                    })
                    .catch(() => {});
            }
        }
    };

    // Initialize on load
    document.addEventListener('DOMContentLoaded', () => CartService.init());

    window.CartService = CartService;
})();