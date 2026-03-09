document.addEventListener('DOMContentLoaded', function() {
    const skuInput = document.getElementById('id_sku');
    const nameInput = document.getElementById('id_product_name');
    const priceInput = document.getElementById('id_price');

    if (!skuInput) return;

    skuInput.addEventListener('change', function() {
        const sku = this.value.trim();
        if (sku) {
            fetch(`../lookup-product-data/?sku=${encodeURIComponent(sku)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.found) {
                        if(nameInput) {
                            nameInput.value = data.name;
                            nameInput.style.backgroundColor = "#e8f0fe";
                        }
                        if(priceInput) {
                            priceInput.value = data.price;
                            priceInput.style.backgroundColor = "#e8f0fe";
                        }
                        setTimeout(() => {
                            if(nameInput) nameInput.style.backgroundColor = "";
                            if(priceInput) priceInput.style.backgroundColor = "";
                        }, 1000);
                    }
                })
                .catch(err => console.error(err));
        }
    });
});