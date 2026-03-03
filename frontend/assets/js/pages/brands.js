// frontend/assets/js/pages/brands.js

let currentPage = 1;
let isLoading = false;
let hasNext = true;

document.addEventListener('DOMContentLoaded', () => {
    // Page load hone par pehla batch laayein
    loadBrands(true);
});

// --- Infinite Scroll Setup ---
function setupBrandScroll() {
    const container = document.getElementById('brands-container');
    if (!container) return;

    const oldSentinel = document.getElementById('brand-sentinel');
    if (oldSentinel) oldSentinel.remove();

    const sentinel = document.createElement('div');
    sentinel.id = 'brand-sentinel';
    sentinel.style.width = '100%';
    sentinel.style.height = '20px';
    sentinel.style.marginBottom = '50px';
    
    container.after(sentinel);

    const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && !isLoading && hasNext) {
            currentPage++;
            loadBrands(false);
        }
    }, { rootMargin: '200px' });

    observer.observe(sentinel);
}

// Loader Functions
function insertSentinelLoader() {
    let loader = document.getElementById('scroll-loader');
    if(!loader) {
        loader = document.createElement('div');
        loader.id = 'scroll-loader';
        loader.className = 'text-center py-3 w-100';
        loader.innerHTML = '<div class="loader-spinner" style="width:30px; height:30px; margin:auto;"></div>';
        document.getElementById('brands-container').after(loader);
    }
}

function removeSentinelLoader() {
    const loader = document.getElementById('scroll-loader');
    if(loader) loader.remove();
}

// Main Load Function
async function loadBrands(reset = false) {
    if (isLoading) return;
    isLoading = true;

    const container = document.getElementById('brands-container');
    
    if (reset) {
        currentPage = 1;
        hasNext = true;
        container.innerHTML = '<div class="loader-spinner"></div>';
    } else {
        insertSentinelLoader();
    }

    try {
        // API mein ?page= parameter bhej rahe hain
        const res = await ApiService.get(`/catalog/brands/?page=${currentPage}`);
        
        let brands = [];
        if (Array.isArray(res)) {
            brands = res;
            hasNext = false; // Agar array hai toh matlab pagination nahi hai
        } else {
            brands = res.results || [];
            hasNext = !!res.next; // res.next mein URL hota hai agar aage data bacha ho
        }

        if (reset) container.innerHTML = '';

        if (brands.length === 0 && currentPage === 1) {
            container.innerHTML = '<p class="text-center w-100">No brands found.</p>';
            hasNext = false;
        } else {
            // Naye brands HTML mein append karein (.fade-in animation ke saath)
            const html = brands.map(b => `
                <div class="brand-card fade-in" onclick="window.location.href='./search_results.html?brand=${b.id}'">
                    <img src="${b.logo_url || b.logo || 'https://via.placeholder.com/80'}" class="brand-logo" alt="${b.name}" loading="lazy">
                    <div style="font-weight:600; font-size:0.9rem;">${b.name}</div>
                </div>
            `).join('');
            
            container.insertAdjacentHTML('beforeend', html);
        }

    } catch (e) {
        console.error("Failed to load brands", e);
        if (currentPage === 1) {
            container.innerHTML = '<p class="text-danger text-center w-100">Failed to load brands.</p>';
        }
    } finally {
        isLoading = false;
        if (!reset) removeSentinelLoader();
        
        if (reset && hasNext) {
            setupBrandScroll(); // Pehli baar load hone ke baad observer lagayein
        }
        
        const s = document.getElementById('brand-sentinel');
        if (s) s.style.display = hasNext ? 'block' : 'none';
    }
}