/* frontend/assets/js/services/cart.service.js */

window.CartService = {
    /**
     * Fetch the current cart from the API.
     */
    async getCart() {
        return window.ApiService.get('/orders/cart/');
    },

    /**
     * Add an item to the cart.
     * [FIXED] Auto-resolves Warehouse ID if missing.
     */
    async addToCart(productId, quantity = 1) {
        try {
            // 1. Get the current Warehouse ID from storage
            let warehouseId = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID);

            // [FIX] Agar Warehouse ID missing hai par Location set hai, toh fetch karo
            if (!warehouseId) {
                console.log("CartService: Warehouse ID missing, attempting to resolve...");
                warehouseId = await this.resolveWarehouseId();
            }

            // Validation: Cannot add to cart if location isn't set OR resolution failed
            if (!warehouseId) {
                // Trigger Location Modal if available to force user selection
                if (window.ServiceCheck && typeof window.ServiceCheck.init === 'function') {
                    window.ServiceCheck.init();
                }
                throw new Error("Please select your delivery location first.");
            }

            // 2. Construct Payload matching Backend expectations
            const payload = { 
                sku: productId,
                quantity: quantity, 
                warehouse_id: warehouseId 
            };

            const res = await window.ApiService.post('/orders/cart/add/', payload);
            
            window.Toast.success('Item added to cart');
            this.updateGlobalCount(); // Refresh the badge
            return res;
        } catch (error) {
            console.error('Add to cart failed:', error);
            window.Toast.error(error.message || 'Failed to add item');
            throw error;
        }
    },

    // [NEW METHOD] Resolves Warehouse ID using stored Lat/Lng
    async resolveWarehouseId() {
        if (!window.LocationManager || !window.ApiService) return null;

        // Try Delivery Context (L2) first, then Service Context (L1)
        const delivery = window.LocationManager.getDeliveryContext();
        const service = window.LocationManager.getServiceContext();
        
        // Jo bhi location available ho use karein
        const loc = (delivery && delivery.lat) ? delivery : service;

        if (!loc || !loc.lat || !loc.lng) return null;

        try {
            // Backend call to find warehouse for these coordinates
            const res = await window.ApiService.post('/warehouse/find-serviceable/', {
                latitude: loc.lat,
                longitude: loc.lng,
                city: loc.city || ''
            });

            if (res && res.serviceable && res.warehouse && res.warehouse.id) {
                const whId = res.warehouse.id;
                console.log("CartService: Auto-Resolved Warehouse ID:", whId);
                localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID, whId);
                return whId;
            }
        } catch (e) {
            console.warn("Auto-resolve warehouse failed", e);
        }
        return null;
    },

    // Backwards-compatible alias
    async addItem(productId, quantity = 1) {
        return this.addToCart(productId, quantity);
    },

    async updateItem(skuCode, quantity) {
        return this.addToCart(skuCode, quantity); 
    },

    async removeItem(itemId) {
        try {
            await window.ApiService.delete(`/orders/cart/item/${itemId}/`);
            window.Toast.info('Item removed');
            this.updateGlobalCount();
            
            if (window.location.pathname.includes('cart.html')) {
                window.location.reload(); 
            }
        } catch (error) {
            console.error('Remove item failed:', error);
            window.Toast.error('Failed to remove item');
        }
    },

    async updateGlobalCount() {
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

    updateBadgeUI(count) {
        const badges = document.querySelectorAll('.cart-count');
        badges.forEach(el => {
            el.innerText = count;
            el.style.display = count > 0 ? 'flex' : 'none'; 
        });
    },

    // ==========================================
    // LOCATION & VALIDATION LOGIC
    // ==========================================

    initListener() {
        if (window.APP_CONFIG && window.APP_CONFIG.EVENTS) {
            window.addEventListener(window.APP_CONFIG.EVENTS.LOCATION_CHANGED, async () => {
                await this.validateCartOnLocationChange();
            });
        }
    },

    async validateCartOnLocationChange() {
        const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
        if (!token) return; 

        if (!window.LocationManager) return;

        const deliveryCtx = window.LocationManager.getDeliveryContext();
        const serviceCtx = window.LocationManager.getServiceContext();
        
        let payload = {};
        
        if (deliveryCtx && deliveryCtx.id) {
            payload = { address_id: deliveryCtx.id };
        } else if (serviceCtx && serviceCtx.lat) {
            payload = { lat: serviceCtx.lat, lng: serviceCtx.lng };
        } else {
            return; 
        }

        try {
            const res = await window.ApiService.post('/orders/validate-cart/', payload);

            if (res.warehouse_id) {
                localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID, res.warehouse_id);
            }

            if (res.is_valid === false) {
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
            window.ApiService.post('/orders/cart/clear/', {})
                .then(() => {
                    this.updateGlobalCount();
                    window.Toast.info("Cart cleared for new location.");
                })
                .catch(() => {
                    console.log("Auto-clear failed, user must clear manually.");
                    window.Toast.error("Please clear your cart manually.");
                });
        }
    }
};

window.CartService.initListener();