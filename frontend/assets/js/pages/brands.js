document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('brands-container');
    try {
        const res = await ApiService.get('/catalog/brands/');
        const brands = res.results || res;

        if (brands.length === 0) {
            container.innerHTML = '<p class="text-center w-100">No brands found.</p>';
            return;
        }

        container.innerHTML = brands.map(b => `
            <div class="brand-card" onclick="window.location.href='./search_results.html?brand=${b.id}'">
                <img src="${b.logo_url || 'https://via.placeholder.com/80'}" class="brand-logo" alt="${b.name}">
                <div style="font-weight:600; font-size:0.9rem;">${b.name}</div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = '<p class="text-danger text-center w-100">Failed to load brands.</p>';
    }
});
