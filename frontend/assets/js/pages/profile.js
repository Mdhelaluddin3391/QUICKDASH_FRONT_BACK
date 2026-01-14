// frontend/assets/js/pages/profile.js

document.addEventListener('DOMContentLoaded', initDashboard);

/* =========================
   INITIALIZATION
========================= */
async function initDashboard() {
    if (!isAuthenticated()) {
        window.location.href = window.APP_CONFIG.ROUTES.LOGIN;
        return;
    }

    // 1. Initial Render from LocalStorage (Optimistic UI)
    const storedUser = getStoredUser();
    if (storedUser) renderUserInfo(storedUser);

    // 2. Bind Events
    bindEvents();

    // 3. Fetch Fresh Data
    await Promise.all([
        loadProfile(),
        loadStats(),
        loadRecentOrders()
    ]);
}

/* =========================
   AUTH HELPERS
========================= */
function isAuthenticated() {
    return Boolean(localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.TOKEN));
}

function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.USER) || '{}');
    } catch (e) { return {}; }
}

/* =========================
   EVENT BINDINGS
========================= */
function bindEvents() {
    const profileForm = document.getElementById('profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', updateProfile);
    }

    const editBtn = document.getElementById('edit-profile-btn');
    if (editBtn) {
        editBtn.addEventListener('click', openEditModal);
    }

    const logoutBtn = document.getElementById('logout-btn-page');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', window.logout);
    }

    // Modal Close
    const closeBtns = document.querySelectorAll('.close-modal');
    closeBtns.forEach(btn => btn.addEventListener('click', closeProfileModal));
}

/* =========================
   USER INFO & PROFILE
========================= */
function renderUserInfo(user) {
    const nameEl = document.getElementById('user-name');
    if (nameEl) nameEl.innerText = user.first_name ? `${user.first_name} ${user.last_name || ''}` : 'User';

    const phoneEl = document.getElementById('user-phone');
    if (phoneEl) phoneEl.innerText = user.phone || '';

    const greeting = document.getElementById('user-greeting');
    if (greeting) greeting.innerText = user.first_name || 'User';

    // Pre-fill edit form
    const pName = document.getElementById('p-name');
    if (pName) pName.value = `${user.first_name || ''} ${user.last_name || ''}`.trim();
    
    const pEmail = document.getElementById('p-email');
    if (pEmail) pEmail.value = user.email || '';
    
    const pPhone = document.getElementById('p-phone');
    if (pPhone) pPhone.value = user.phone || '';
}

async function loadProfile() {
    try {
        const user = await window.ApiService.get('/auth/profile/');
        // Update Local Storage with fresh data
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));
        renderUserInfo(user);
    } catch (err) {
        console.error("Profile Load Error", err);
    }
}

async function updateProfile(e) {
    e.preventDefault();

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = 'Saving...';

    // Split Name Logic
    const fullName = document.getElementById('p-name').value.trim();
    const nameParts = fullName.split(' ');
    const first_name = nameParts[0];
    const last_name = nameParts.slice(1).join(' ');
    const email = document.getElementById('p-email').value;

    const payload = { first_name, last_name, email };

    try {
        const updatedUser = await window.ApiService.patch('/auth/profile/', payload);
        
        window.Toast.success('Profile Updated');
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(updatedUser));
        renderUserInfo(updatedUser);
        closeProfileModal();

    } catch (err) {
        window.Toast.error(err.message || 'Update failed');
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

function openEditModal() {
    const modal = document.getElementById('profile-modal');
    if (modal) modal.classList.remove('d-none');
}

window.closeProfileModal = function () {
    const modal = document.getElementById('profile-modal');
    if (modal) modal.classList.add('d-none');
};

/* =========================
   STATS LOGIC
========================= */
async function loadStats() {
    try {
        // [FIX] Correct Endpoint: /orders/my-orders/
        const res = await window.ApiService.get('/orders/my-orders/');
        const orders = res.results || res;

        const totalOrdersEl = document.getElementById('total-orders');
        if (totalOrdersEl) totalOrdersEl.innerText = orders.length;

        // Calculate Total Spent
        const totalSpent = orders.reduce(
            (sum, o) => sum + Number(o.final_amount || o.total_amount || 0),
            0
        );

        const totalSpentEl = document.getElementById('total-spent');
        if (totalSpentEl) totalSpentEl.innerText = window.Formatters.currency(totalSpent);

    } catch (err) {
        console.warn('Failed to load stats', err);
    }
}

/* =========================
   RECENT ORDERS
========================= */
async function loadRecentOrders() {
    const container = document.getElementById('recent-orders-list');
    if (!container) return;

    try {
        // [FIX] Correct Endpoint and Params
        const res = await window.ApiService.get('/orders/my-orders/?page_size=3');
        const orders = res.results || res;

        if (!orders.length) {
            container.innerHTML = '<p class="text-muted text-center py-3">No orders yet.</p>';
            return;
        }

        container.innerHTML = orders.map(renderOrderCard).join('');
    } catch (e) {
        console.error(e);
        container.innerHTML = '<p class="text-danger text-center">Failed to load orders</p>';
    }
}

function renderOrderCard(order) {
    const dateStr = new Date(order.created_at).toLocaleDateString();
    const amount = order.final_amount || order.total_amount || 0;
    
    return `
        <div class="order-card" onclick="window.location.href='order_detail.html?id=${order.id}'" style="cursor:pointer; border-bottom:1px solid #eee; padding:10px 0;">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong>Order #${order.id}</strong>
                    <p class="text-muted small mb-0">${dateStr}</p>
                </div>
                <div class="text-right">
                    <span class="badge badge-secondary mb-1">${order.status}</span>
                    <div class="font-weight-bold">
                        ${window.Formatters.currency(amount)}
                    </div>
                </div>
            </div>
        </div>
    `;
}