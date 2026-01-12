// frontend/assets/js/services/cart.service.js

window.CartService = {
    // [FIX 4] Local Placeholder for resilience
    DEFAULT_IMG: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' fill='%23f0f0f0'/%3E%3Ctext x='50' y='50' font-family='Arial' font-size='14' fill='%23999' text-anchor='middle' dy='.3em'%3ENo Image%3C/text%3E%3C/svg%3E",

    async getCart() {
        // [FIX 1] Prevent API call if user is not logged in
        const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
        if (!token) {
            // Return mock empty cart structure for guests
            return Promise.resolve({ items: [], total_amount: 0 });
        }
        return window.ApiService.get('/orders/cart/');
    },

    async addToCart(productId, quantity = 1) {
        try {
            // 1. Auth Check (Optional: depending on business logic, usually required for Cart API)
            const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
            if (!token) {
                window.Toast.warning("Please login to add items.");
                setTimeout(() => window.location.href = window.APP_CONFIG.ROUTES.LOGIN, 1500);
                return;
            }

            // 2. Warehouse Resolution
            const storageKey = window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID || 'current_warehouse_id';
            let warehouseId = localStorage.getItem(storageKey);

            if (!warehouseId) {
                console.log("CartService: ID missing, attempting to resolve...");
                try {
                    warehouseId = await this.resolveWarehouseId();
                } catch (resolutionError) {
                    // [FIX 2] Bubble up specific resolution errors
                    throw resolutionError;
                }
            }

            // 3. Add Item
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
            // Show the specific error message from the backend or resolution logic
            window.Toast.error(error.message || 'Failed to add item');
            
            // If it's a location issue, trigger the picker
            if (error.code === 'LOCATION_REQUIRED') {
                if (window.ServiceCheck && window.ServiceCheck.init) {
                    window.ServiceCheck.init();
                }
            }
        }
    },

    async addItem(productId, quantity = 1) {
        return this.addToCart(productId, quantity);
    },

    async resolveWarehouseId() {
        if (!window.LocationManager) return null;

        const delivery = window.LocationManager.getDeliveryContext();
        const service = window.LocationManager.getServiceContext();
        const loc = (delivery && delivery.lat) ? delivery : service;

        // Case A: No Location Selected
        if (!loc || !loc.lat || !loc.lng) {
            const err = new Error("Please select your delivery location first.");
            err.code = 'LOCATION_REQUIRED';
            throw err;
        }

        try {
            const res = await window.ApiService.post('/warehouse/find-serviceable/', {
                latitude: loc.lat,
                longitude: loc.lng
            });

            // Case B: Location Serviceable
            if (res && res.serviceable && res.warehouse && res.warehouse.id) {
                const key = window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID || 'current_warehouse_id';
                localStorage.setItem(key, res.warehouse.id);
                return res.warehouse.id;
            } 
            
            // Case C: Location Found but Not Serviceable
            const areaName = loc.area_name || loc.city || "your location";
            throw new Error(`Sorry, we do not deliver to ${areaName} yet.`);

        } catch (e) {
            // If it's our own error, rethrow it
            if (e.message && e.message.includes("not deliver")) throw e;
            
            console.warn("Could not auto-resolve warehouse:", e);
            throw new Error("Unable to check availability. Please try again.");
        }
    },

    async removeItem(itemId) {
        try {
            await window.ApiService.delete(`/orders/cart/item/${itemId}/`);
            window.Toast.info('Item removed');
            this.updateGlobalCount();
            // Refresh if on cart page
            if (window.location.pathname.includes('cart.html')) {
                // Use loadCart if available globally, else reload
                if (typeof window.loadCart === 'function') {
                    await window.loadCart();
                } else {
                    window.location.reload();
                }
            }
        } catch (error) {
            window.Toast.error('Failed to remove item');
        }
    },

    async updateGlobalCount() {
        // [FIX 1] Double check here too for safety
        const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
        if (!token) {
            this.updateBadgeUI(0);
            return; 
        }

        try {
            // This now safely returns { items: [] } if token is missing/invalid
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

    async updateItem(skuCode, qty) {
        // Helper for cart page qty updates
        const warehouseId = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID);
        return window.ApiService.post('/orders/cart/add/', {
            sku: skuCode,
            quantity: qty,
            warehouse_id: warehouseId
        });
    },

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
        
        // Priority: Delivery Address > Service Location
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
        const itemName = items.length > 0 ? items[0].product_name : "Items";
        const msg = items.length > 0 
            ? `${itemName} and others are not available at this new location.`
            : "Your cart items are from a different store.";
            
        if (confirm(`⚠️ Location Changed\n\n${msg}\n\nDo you want to clear your cart to shop here?`)) {
            window.ApiService.post('/orders/cart/add/', { force_clear: true, sku: 'DUMMY', quantity: 0 })
                .then(() => {
                    this.updateGlobalCount();
                    window.Toast.info("Cart cleared for new location.");
                    if (window.location.pathname.includes('cart.html')) window.location.reload();
                })
                .catch(() => {
                    // Fallback manual clear logic
                });
        }
    }
};

// Initialize Listener
if(window.CartService && window.CartService.initListener) {
    window.CartService.initListener();
}