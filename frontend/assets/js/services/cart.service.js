// frontend/assets/js/services/cart.service.js

/**
 * CartService: Singleton for managing Cart State & API calls.
 * Dependencies: ApiService, APP_CONFIG
 */
(function () {
    const CartService = {
        _count: 0,
        _total: 0,

        /**
         * Initialize: Fetch count on load
         */
        init: async function() {
            if (localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN)) {
                await this.updateGlobalCount();
            }
            this.initListener();
        },

        /**
         * Fetch latest cart from backend and update UI
         */
        getCart: async function () {
            try {
                // ApiService injects Location Headers automatically
                const res = await window.ApiService.get('/orders/cart/');
                
                // Update internal state
                this._total = res.total_amount || 0;
                this._count = (res.items || []).length;
                
                // Notify UI
                this._notifyChange(res);
                return res;
            } catch (error) {
                console.error("CartService: Get failed", error);
                throw error;
            }
        },

        /**
         * Add Item to Cart
         * @param {string} sku - Product SKU Code
         * @param {number} qty - Quantity
         */
        addItem: async function (sku, qty = 1) {
            return this.updateItem(sku, qty);
        },

        /**
         * Update Item Quantity (Add/Remove/Update)
         */
        updateItem: async function (sku, qty) {
            try {
                // Note: Warehouse ID is handled by Backend Middleware via Headers
                // We don't need to send it explicitly unless overriding
                
                const res = await window.ApiService.post('/orders/cart/add/', {
                    sku: sku,
                    quantity: qty
                });

                // Update internal state from response
                this._total = res.total_amount || 0;
                this._count = (res.items || []).length;
                
                this._notifyChange(res);
                return res;

            } catch (error) {
                // Handle Warehouse Mismatch specifically if not caught by ApiService
                // (Though ApiService usually catches 409 globally)
                if (error.message && error.message.includes("Location Mismatch")) {
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

        /**
         * Clear Cart
         */
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

        /**
         * Updates the little badge in the Navbar
         */
        updateGlobalCount: async function () {
            try {
                const res = await window.ApiService.get('/orders/cart/');
                this._count = (res.items || []).length;
                this._updateBadges();
            } catch (e) { 
                // Silent fail if guest or error
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
            if (window.APP_CONFIG && window.APP_CONFIG.EVENTS) {
                // Listen for Location Changes to re-validate cart if needed
                window.addEventListener(window.APP_CONFIG.EVENTS.LOCATION_CHANGED, async () => {
                    await this.validateCartOnLocationChange();
                });
            }
        },

        async validateCartOnLocationChange() {
            const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
            if (!token) return; 

            // ApiService will send new location headers automatically
            try {
                const res = await window.ApiService.post('/orders/validate-cart/', {});
                
                if (res.is_valid === false) {
                    this.showConflictModal(res.unavailable_items || []);
                }
            } catch (e) {
                console.warn("Cart validation check failed", e);
            }
        },

        showConflictModal(items) {
            const itemName = items.length > 0 ? items[0].product_name : "Items";
            const msg = items.length > 0 
                ? `${itemName} and others are not available at this new location.`
                : "Your cart items are from a different store.";
                
            if (confirm(`⚠️ Location Changed\n\n${msg}\n\nDo you want to clear your cart to shop here?`)) {
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