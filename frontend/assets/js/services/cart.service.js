// frontend/assets/js/services/cart.service.js

window.CartService = {
    // Placeholder Image
    DEFAULT_IMG: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' fill='%23f0f0f0'/%3E%3Ctext x='50' y='50' font-family='Arial' font-size='14' fill='%23999' text-anchor='middle' dy='.3em'%3ENo Image%3C/text%3E%3C/svg%3E",

    async getCart() {
        const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
        // User logged in nahi hai toh API call mat karo
        if (!token) {
            return Promise.resolve({ items: [], total_amount: 0 });
        }
        return window.ApiService.get('/orders/cart/');
    },

    async addToCart(productId, quantity = 1) {
        try {
            // 1. Auth Check
            const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN);
            if (!token) {
                // Yahan se error throw karenge taaki caller handle kare
                // Note: Aap chahein to yahan redirect logic rakh sakte hain, par error throw karna zaruri hai
                const err = new Error("Please login to add items.");
                err.code = 'AUTH_REQUIRED';
                throw err;
            }

            // 2. Warehouse Resolution
            const storageKey = window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID || 'current_warehouse_id';
            let warehouseId = localStorage.getItem(storageKey);

            if (!warehouseId) {
                console.log("CartService: ID missing, attempting to resolve...");
                try {
                    warehouseId = await this.resolveWarehouseId();
                } catch (resolutionError) {
                    // Agar location issue hai toh error upar bhejo
                    throw resolutionError;
                }
            }

            // 3. Add Item API Call
            const payload = { 
                sku: productId,
                quantity: quantity, 
                warehouse_id: warehouseId 
            };

            const res = await window.ApiService.post('/orders/cart/add/', payload);
            
            // [FIX 1] REMOVED SUCCESS TOAST FROM HERE
            // Ab 'product.js' ya 'home.js' success message dikhayega.
            
            this.updateGlobalCount();
            return res;

        } catch (error) {
            console.error('Add to cart failed:', error);
            
            // [FIX 2] REMOVED ERROR TOAST FROM HERE
            // Taaki do baar message na aaye.

            // Handle Login Redirect explicitly if needed, otherwise caller handles it
            if (error.code === 'AUTH_REQUIRED') {
                 window.Toast.warning(error.message);
                 setTimeout(() => window.location.href = window.APP_CONFIG.ROUTES.LOGIN, 1500);
                 // Still throw error to stop the "Success" message on the other page
                 throw error; 
            }

            // Location Service Trigger logic
            if (error.code === 'LOCATION_REQUIRED') {
                if (window.ServiceCheck && window.ServiceCheck.init) {
                    window.ServiceCheck.init();
                }
            }

            // [CRITICAL FIX] Error ko wapas fekna (Throw) zaruri hai
            throw error;
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
            // Agar ye "do not deliver" wala error hai, toh seedha wahi bhejo
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
            
            if (window.location.pathname.includes('cart.html')) {
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

    async updateItem(skuCode, qty) {
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
                .catch(() => {});
        }
    }
};

// Initialize Listener
if(window.CartService && window.CartService.initListener) {
    window.CartService.initListener();
}