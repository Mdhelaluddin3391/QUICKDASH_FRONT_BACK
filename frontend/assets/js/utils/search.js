/**
 * Advanced Navbar Search Auto-complete & Redirection
 */
window.SearchManager = {
    input: null,
    form: null,
    debounceTimer: null,
    suggestionBox: null,

    init() {
        // Yahan 'id="search-input"' ka use kiya gaya hai jo humne html me banaya tha
        this.input = document.getElementById('search-input'); 
        this.form = document.querySelector('.search-bar-row');
        // Jo div humne HTML mein add kiya tha, usi ko directly utha rahe hain
        this.suggestionBox = document.getElementById('search-suggestions-box');
        this.debounceTimer = null;

        if (this.input && this.form && this.suggestionBox) {
            this.setup();
        } else {
            console.warn("Search elements not found on the page.");
        }
    },

    setup() {
        // Dropdown styling ab hum JS se apply kar rahe hain, in case HTML me mix na ho
        this.suggestionBox.style.cssText = `
            display: none; position: absolute; top: calc(100% + 5px); left: 0; right: 0;
            background: #ffffff; border: 1px solid #e2e8f0;
            border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            z-index: 1000; overflow: hidden; max-height: 450px; overflow-y: auto;
            transition: all 0.2s ease-in-out;
        `;
        
        // Input handle karna
        this.input.addEventListener('input', (e) => this.handleInput(e));
        
        // Focus karne pe wapas purana result kholna agar type kiya hua hai
        this.input.addEventListener('focus', (e) => { 
            if(e.target.value.trim().length > 1) this.showSuggestions(); 
        });
        
        // Bahar click karne pe dropdown band karna
        document.addEventListener('click', (e) => {
            if (!this.form.contains(e.target) && !this.suggestionBox.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    },

    handleInput(e) {
        const query = e.target.value.trim();
        clearTimeout(this.debounceTimer);
        
        if (query.length < 2) {
            this.hideSuggestions();
            this.suggestionBox.innerHTML = '';
            return;
        }
        
        // Loading Indicator
        this.suggestionBox.innerHTML = `<div style="padding: 15px; text-align: center; color: #888; font-size: 0.9rem;"><i class="fas fa-spinner fa-spin" style="margin-right:8px;"></i> Searching for "${query}"...</div>`;
        this.showSuggestions();

        // 300ms ruk kar call karenge
        this.debounceTimer = setTimeout(() => this.fetchSuggestions(query), 300);
    },

    async fetchSuggestions(query) {
        try {
            // Yahan dhyan rakhein, aapke code mein ApiService.get use ho raha tha, 
            // agar API service globally set hai toh chalega, warna normal fetch best rehta hai.
            // Main safe fetch use kar raha hu taki error na aaye.
            
            const apiUrl = window.CONFIG?.API_URL || 'http://127.0.0.1:8000';
            const response = await fetch(`${apiUrl}/api/catalog/search/suggest/?q=${encodeURIComponent(query)}`);
            
            if(response.ok) {
                const res = await response.json();
                this.renderSuggestions(res, query);
            } else {
                throw new Error("API Response not ok");
            }
            
        } catch (e) { 
            console.error("Search suggestion failed", e);
            this.suggestionBox.innerHTML = `<div style="padding: 15px; text-align: center; color: #e74c3c; font-size: 0.9rem;">Something went wrong. Please try again.</div>`;
        }
    },

    // Matches highlight karne ka function
    highlightMatch(text, query) {
        if (!query || !text) return text;
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<span style="color: #ff3c6e; font-weight: 700;">$1</span>');
    },

    renderSuggestions(items, query) {
        if (!items || items.length === 0) {
            this.suggestionBox.innerHTML = `<div style="padding: 15px; text-align: center; color: #6c757d; font-size: 0.9rem;">No results found for "<b>${query}</b>"</div>`;
            return;
        }

        const html = items.map(item => {
            const highlightedText = this.highlightMatch(item.text, query);
            const imageHtml = item.image 
                ? `<img src="${item.image}" style="width: 100%; height: 100%; object-fit: cover;" alt="thumb">` 
                : `<i class="fas fa-${item.type === 'Brand' ? 'tag' : 'box'} text-muted" style="font-size: 1.2rem;"></i>`;

            return `
            <a href="${item.url}" style="text-decoration: none; color: inherit; display: block;">
                <div class="suggestion-item" style="padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #f1f5f9; display: flex; align-items: center; transition: background 0.2s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
                    <div style="width: 40px; height: 40px; border-radius: ${item.type === 'Brand' ? '50%' : '6px'}; border: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: center; margin-right: 12px; overflow: hidden; background: #f8f9fa; flex-shrink: 0;">
                        ${imageHtml}
                    </div>
                    <div style="flex-grow: 1; min-width: 0;">
                        <div style="font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px;">${highlightedText}</div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <small style="color: #64748b; font-size: 12px;">in ${item.type}</small>
                            ${item.price ? `<small style="font-weight: bold; color: #ff3c6e; font-size: 13px;">₹${item.price}</small>` : ''}
                        </div>
                    </div>
                </div>
            </a>`;
        }).join('');
        
        // Form submit karne ke liye
        const viewAllHtml = `
            <div style="padding: 12px; text-align: center; background: #f8fafc; cursor: pointer; color: #ff3c6e; font-weight: 600; font-size: 0.9rem; border-top: 1px solid #e2e8f0; transition: background 0.2s;"
                 onmouseover="this.style.background='#ffe5eb'" onmouseout="this.style.background='#f8fafc'"
                 onclick="document.querySelector('.search-bar-row').submit()">
                View all results <i class="fas fa-arrow-right ms-1" style="font-size: 0.8rem;"></i>
            </div>
        `;

        this.suggestionBox.innerHTML = html + viewAllHtml;
        this.showSuggestions();
    },

    showSuggestions() { 
        this.suggestionBox.style.display = 'block'; 
        this.suggestionBox.classList.remove('d-none');
    },
    hideSuggestions() { 
        this.suggestionBox.style.display = 'none'; 
        this.suggestionBox.classList.add('d-none');
    }
};

document.addEventListener('DOMContentLoaded', () => SearchManager.init());