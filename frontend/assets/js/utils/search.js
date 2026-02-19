/**
 * Advanced Navbar Search Auto-complete & Redirection
 */
window.SearchManager = {
    input: null,
    form: null,
    debounceTimer: null,
    suggestionBox: null,

    init() {
        this.input = document.querySelector('input[name="search"]');
        this.form = document.querySelector('.search-bar-row');
        this.debounceTimer = null;
        this.suggestionBox = null;

        if (this.input && this.form) {
            this.setup();
        }
    },

    setup() {
        this.suggestionBox = document.createElement('div');
        this.suggestionBox.className = 'search-suggestions d-none';
        
        // Advanced Solid UI Styling
        this.suggestionBox.style.cssText = `
            position: absolute; top: calc(100% + 5px); left: 0; right: 0;
            background: #ffffff; border: 1px solid #e2e8f0;
            border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            z-index: 1000; overflow: hidden; max-height: 450px; overflow-y: auto;
            transition: all 0.2s ease-in-out;
        `;
        this.form.style.position = 'relative'; 
        this.form.appendChild(this.suggestionBox);

        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('focus', (e) => { if(e.target.value.trim().length > 1) this.showSuggestions(); });
        
        document.addEventListener('click', (e) => {
            if (!this.form.contains(e.target)) this.hideSuggestions();
        });
    },

    handleInput(e) {
        const query = e.target.value.trim();
        clearTimeout(this.debounceTimer);
        
        if (query.length < 2) {
            this.hideSuggestions();
            return;
        }
        
        // Loading Indicator while fetching
        this.suggestionBox.innerHTML = `<div style="padding: 15px; text-align: center; color: #888; font-size: 0.9rem;"><i class="fas fa-spinner fa-spin"></i> Searching for "${query}"...</div>`;
        this.showSuggestions();

        this.debounceTimer = setTimeout(() => this.fetchSuggestions(query), 300);
    },

    async fetchSuggestions(query) {
        try {
            const res = await ApiService.get(`/catalog/search/suggest/?q=${encodeURIComponent(query)}`);
            this.renderSuggestions(res, query);
        } catch (e) { 
            console.warn("Search suggestion failed", e);
            this.suggestionBox.innerHTML = `<div style="padding: 15px; text-align: center; color: #e74c3c; font-size: 0.9rem;">Something went wrong. Please try again.</div>`;
        }
    },

    // Highlights typed characters in the search results
    highlightMatch(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<span style="color: var(--primary, #d32f2f); font-weight: 700;">$1</span>');
    },

    renderSuggestions(items, query) {
        if (!items || items.length === 0) {
            this.suggestionBox.innerHTML = `<div style="padding: 15px; text-align: center; color: #6c757d; font-size: 0.9rem;">No results found for "<b>${query}</b>"</div>`;
            return;
        }

        const html = items.map(item => {
            const highlightedText = this.highlightMatch(item.text, query);
            const imageHtml = item.image 
                ? `<img src="${item.image}" style="width: 100%; height: 100%; object-fit: contain;" alt="thumb">` 
                : `<i class="fas fa-${item.type === 'Brand' ? 'tag' : 'box'} text-muted" style="font-size: 1.2rem;"></i>`;

            return `
            <a href="${item.url}" style="text-decoration: none; color: inherit; display: block;">
                <div class="suggestion-item" style="padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #f1f5f9; display: flex; align-items: center; transition: background 0.2s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
                    <div style="width: 40px; height: 40px; border-radius: ${item.type === 'Brand' ? '50%' : '6px'}; border: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: center; margin-right: 12px; overflow: hidden; background: #fff; flex-shrink: 0;">
                        ${imageHtml}
                    </div>
                    <div style="flex-grow: 1; min-width: 0;">
                        <div style="font-weight: 500; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px;">${highlightedText}</div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <small style="color: #64748b; font-size: 0.75rem;">in ${item.type}</small>
                            ${item.price ? `<small style="font-weight: 600; color: #334155; font-size: 0.8rem;">₹${item.price}</small>` : ''}
                        </div>
                    </div>
                </div>
            </a>`;
        }).join('');
        
        const viewAllHtml = `
            <div style="padding: 12px; text-align: center; background: #f8fafc; cursor: pointer; color: var(--primary, #0d6efd); font-weight: 600; font-size: 0.9rem; border-top: 1px solid #e2e8f0; transition: background 0.2s;"
                 onmouseover="this.style.background='#e2e8f0'" onmouseout="this.style.background='#f8fafc'"
                 onclick="document.querySelector('.search-bar-row form').submit()">
                View all results <i class="fas fa-arrow-right ms-1" style="font-size: 0.8rem;"></i>
            </div>
        `;

        this.suggestionBox.innerHTML = html + viewAllHtml;
        this.showSuggestions();
    },

    showSuggestions() { this.suggestionBox.classList.remove('d-none'); },
    hideSuggestions() { this.suggestionBox.classList.add('d-none'); }
};

document.addEventListener('DOMContentLoaded', () => SearchManager.init());