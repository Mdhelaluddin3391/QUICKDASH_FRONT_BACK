// frontend/assets/js/services/cart.service.js

window.CartService = {
    async getCart() {
        return window.ApiService.get('/orders/cart/');
    },

    async addToCart(productId, quantity = 1) {
        try {
            const storageKey = window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID || 'current_warehouse_id';
            let warehouseId = localStorage.getItem(storageKey);

            if (!warehouseId) {
                console.log("CartService: ID missing, attempting to resolve...");
                warehouseId = await this.resolveWarehouseId();
            }

            if (!warehouseId) {
                if (window.ServiceCheck && window.ServiceCheck.init) {
                    window.ServiceCheck.init();
                }
                throw new Error("Please select your delivery location first.");
            }

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

    async addItem(productId, quantity = 1) {
        return this.addToCart(productId, quantity);
    },

    async resolveWarehouseId() {
        if (!window.LocationManager) return null;

        const delivery = window.LocationManager.getDeliveryContext();
        const service = window.LocationManager.getServiceContext();
        const loc = (delivery && delivery.lat) ? delivery : service;

        if (!loc || !loc.lat || !loc.lng) return null;

        try {
            const res = await window.ApiService.post('/warehouse/find-serviceable/', {
                latitude: loc.lat,
                longitude: loc.lng
            });

            if (res && res.warehouse && res.warehouse.id) {
                const key = window.APP_CONFIG.STORAGE_KEYS.WAREHOUSE_ID || 'current_warehouse_id';
                localStorage.setItem(key, res.warehouse.id);
                return res.warehouse.id;
            } else {
                // If resolving specifically fails for an active location context
                console.warn("Location found but not serviceable during resolve.");
                // Optional: window.location.href = 'not_serviceable.html';
            }
        } catch (e) {
            console.warn("Could not auto-resolve warehouse:", e);
        }
        return null;
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
                    window.Toast.error("Please clear your cart manually.");
                });
        }
    }
};

window.CartService.initListener();