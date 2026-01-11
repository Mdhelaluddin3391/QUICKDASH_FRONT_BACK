/* frontend/assets/js/services/cart.service.js */

window.CartService = {
    /**
     * Fetch the current cart from the API.
     */
    async getCart() {
        return window.ApiService.get('/orders/cart/');
    },

    /**
     * [FIXED] Add Item with Auto-Resolve Logic
     */
    async addToCart(productId, quantity = 1) {
        try {
            // 1. Try to get ID from storage
            // Note: We use the config key to ensure we match your system's naming
            const storageKey = window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID || 'current_warehouse_id';
            let warehouseId = localStorage.getItem(storageKey);

            // 2. If missing, attempt to auto-resolve it from current location
            if (!warehouseId) {
                console.log("CartService: ID missing, attempting to resolve...");
                warehouseId = await this.resolveWarehouseId();
            }

            // 3. If STILL missing, user really hasn't selected a location
            if (!warehouseId) {
                // Trigger the location modal if it exists
                if (window.ServiceCheck && window.ServiceCheck.init) {
                    window.ServiceCheck.init();
                }
                throw new Error("Please select your delivery location first.");
            }

            // 4. Send request with valid ID
            const payload = { 
                sku: productId,
                quantity: quantity, 
                warehouse_id: warehouseId 
            };

            const res = await window.ApiService.post('/orders/cart/add/', payload);
            window.Toast.success('Item added to cart');
            this.updateGlobalCount();
            return res;

        } catch (error) {
            console.error('Add to cart failed:', error);
            window.Toast.error(error.message || 'Failed to add item');
            throw error;
        }
    },

    // Backwards-compatible alias used around the codebase
    async addItem(productId, quantity = 1) {
        return this.addToCart(productId, quantity);
    },



    async resolveWarehouseId() {
        if (!window.LocationManager) return null;

        // Try to get any valid coordinates from LocationManager
        const delivery = window.LocationManager.getDeliveryContext(); // Precise Address
        const service = window.LocationManager.getServiceContext();   // General Area
        const loc = (delivery && delivery.lat) ? delivery : service;

        if (!loc || !loc.lat || !loc.lng) return null;

        try {
            // Ask backend which warehouse covers this spot
            const res = await window.ApiService.post('/warehouse/find-serviceable/', {
                latitude: loc.lat,
                longitude: loc.lng
            });

            if (res && res.warehouse && res.warehouse.id) {
                const key = window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID || 'current_warehouse_id';
                localStorage.setItem(key, res.warehouse.id);
                return res.warehouse.id;
            }
        } catch (e) {
            console.warn("Could not auto-resolve warehouse:", e);
        }
        return null;
    },

    /**
     * Update existing item (alias for add in some contexts)
     */
    async updateItem(skuCode, quantity) {
        // Reuse addToCart logic if backend handles updates this way
        return this.addToCart(skuCode, quantity); 
    },

    /**
     * Remove an item from the cart.
     */
    async removeItem(itemId) {
        try {
            await window.ApiService.delete(`/orders/cart/item/${itemId}/`);
            window.Toast.info('Item removed');
            this.updateGlobalCount();
            
            // If we are on the cart page, reload to refresh the list
            if (window.location.pathname.includes('cart.html')) {
                window.location.reload(); 
            }
        } catch (error) {
            console.error('Remove item failed:', error);
            window.Toast.error('Failed to remove item');
        }
    },

    /**
     * Update the global cart count badge in the UI.
     * Handles 401 Unauthorized (Guest Users) gracefully.
     */
    async updateGlobalCount() {
        // [FIX] Check for token BEFORE making the request.
        // If no token exists, the user is a guest; show 0 items immediately.
        const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
        
        if (!token) {
            this.updateBadgeUI(0);
            return; 
        }

        try {
            const cart = await this.getCart();
            let count = 0;
            if (cart && cart.items) {
                count = cart.items.length; 
            }
            this.updateBadgeUI(count);
        } catch (error) {
            console.warn('Failed to update cart count:', error);
            this.updateBadgeUI(0);
        }
    },

    /**
     * Helper to update the DOM elements
     */
    updateBadgeUI(count) {
        const badges = document.querySelectorAll('.cart-count');
        badges.forEach(el => {
            el.innerText = count;
            // Hide badge if count is 0, show otherwise
            el.style.display = count > 0 ? 'flex' : 'none'; 
        });
    },

    // ==========================================
    // LOCATION & VALIDATION LOGIC
    // ==========================================

    initListener() {
        // Ensure APP_CONFIG exists before listening
        if (window.APP_CONFIG && window.APP_CONFIG.EVENTS) {
            window.addEventListener(window.APP_CONFIG.EVENTS.LOCATION_CHANGED, async () => {
                await this.validateCartOnLocationChange();
            });
        }
    },

    async validateCartOnLocationChange() {
        // Only validate for logged-in users (Guest carts might not need strict location checks yet)
        const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
        if (!token) return; 

        // 1. Determine Context to Validate
        if (!window.LocationManager) return;

        const deliveryCtx = window.LocationManager.getDeliveryContext();
        const serviceCtx = window.LocationManager.getServiceContext();
        
        let payload = {};
        
        // Priority: Validate Specific Address (L2) -> Area Browsing (L1)
        if (deliveryCtx && deliveryCtx.id) {
            payload = { address_id: deliveryCtx.id };
        } else if (serviceCtx && serviceCtx.lat) {
            payload = { lat: serviceCtx.lat, lng: serviceCtx.lng };
        } else {
            return; // No location context set
        }

        try {
            // Call Backend Validation
            const res = await window.ApiService.post('/orders/validate-cart/', payload);

            if (res.warehouse_id) {
                // Update local warehouse ID preference
                localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID, res.warehouse_id);
            }

            if (res.is_valid === false) {
                // CONFLICT DETECTED
                this.showConflictModal(res.unavailable_items || []);
            }
        } catch (e) {
            console.warn("Cart validation check failed", e);
        }
    },

    showConflictModal(items) {
        const msg = items.length > 0 
            ? `Items like ${items[0].product_name} are not available at this new location.`
            : "Your cart items are from a different store.";
            
        if (confirm(`⚠️ Location Changed\n\n${msg}\n\nDo you want to clear your cart to shop here?`)) {
            // Clear cart via API
            window.ApiService.post('/orders/cart/clear/', {})
                .then(() => {
                    this.updateGlobalCount();
                    window.Toast.info("Cart cleared for new location.");
                })
                .catch(() => {
                    // Fallback if specific clear endpoint doesn't exist, try adding empty dummy
                    console.log("Auto-clear failed, user must clear manually.");
                    window.Toast.error("Please clear your cart manually.");
                });
        }
    }
};

// Initialize listeners immediately
window.CartService.initListener();