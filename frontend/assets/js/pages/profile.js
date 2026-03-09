document.addEventListener('DOMContentLoaded', initDashboard);

/* =========================
   INITIALIZATION
========================= */
async function initDashboard() {
    // 1. Critical Security Check: User Login Check
    if (!isAuthenticated()) {
        document.body.style.display = 'none'; // Hide content immediately
        const loginUrl = window.APP_CONFIG?.ROUTES?.LOGIN || 'auth.html';
        window.location.replace(loginUrl);
        return;
    }

    // 2. Load Data from LocalStorage (Instant Display)
    const storedUser = getStoredUser();
    if (storedUser && Object.keys(storedUser).length > 0) {
        renderUserInfo(storedUser);
    }

    // 3. Bind Button & Form Events
    bindEvents();

    // 4. Fetch Fresh Data from Server
    try {
        await Promise.all([
            loadProfile(),      // User Profile Details
            loadStats(),        // Dashboard Stats
            loadRecentOrders()  // Recent Orders List
        ]);
    } catch (err) {
        console.warn("Partial data load failure", err);
    }
}

/* =========================
   AUTH HELPERS
========================= */
function isAuthenticated() {
    const tokenKey = window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token';
    const token = localStorage.getItem(tokenKey);
    return token && token !== 'null' && token !== 'undefined' && token.trim() !== '';
}

function getStoredUser() {
    try {
        const userStr = localStorage.getItem(window.APP_CONFIG?.STORAGE_KEYS?.USER);
        return userStr ? JSON.parse(userStr) : {};
    } catch (e) { return {}; }
}

window.ApiService.clearCache(); // Run on init

/* =========================
   EVENT BINDINGS
========================= */
function bindEvents() {
    const profileForm = document.getElementById('profile-form');
    if (profileForm) profileForm.addEventListener('submit', updateProfile);

    const editBtn = document.getElementById('edit-profile-btn');
    if (editBtn) editBtn.addEventListener('click', openEditModal);

    const logoutBtn = document.getElementById('logout-btn-page');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            if (typeof window.logout === 'function') {
                window.logout();
            } else {
                localStorage.clear();
                window.location.href = 'auth.html';
            }
        });
    }

    const closeBtns = document.querySelectorAll('.close-modal, .btn-secondary[data-dismiss="modal"]');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            closeProfileModal();
        });
    });
}

/* =========================
   USER INFO & PROFILE RENDER
========================= */
function renderUserInfo(user) {
    if (!user) return;

    const nameEl = document.getElementById('user-name');
    if (nameEl) {
        let displayName = user.first_name || 'User';
        if (user.first_name && user.last_name) displayName += ` ${user.last_name}`;
        nameEl.innerText = displayName;
    }

    const phoneEl = document.getElementById('user-phone');
    if (phoneEl) {
        const phoneValue = user.phone || user.mobile || '';
        if (phoneValue) {
            phoneEl.innerText = phoneValue;
            phoneEl.style.color = '#333';
        } else {
            phoneEl.innerText = 'Add Phone Number';
            phoneEl.style.color = '#999';
        }
    }

    const greeting = document.getElementById('user-greeting');
    if (greeting) greeting.innerText = user.first_name || 'User';
    
    const avatarEl = document.querySelector('.avatar-circle');
    if (avatarEl) {
        const initial = user.first_name ? user.first_name.charAt(0).toUpperCase() : 'U';
        avatarEl.innerText = initial;
    }

    const editFname = document.getElementById('edit-fname'); 
    if (editFname) editFname.value = user.first_name || '';

    const editLname = document.getElementById('edit-lname');
    if (editLname) editLname.value = user.last_name || '';

    const editEmail = document.getElementById('edit-email'); 
    if (editEmail) editEmail.value = user.email || '';
}

/* =========================
   API: LOAD & UPDATE PROFILE
========================= */
async function loadProfile() {
    try {
        const user = await window.ApiService.get('/customers/me/');
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));
        renderUserInfo(user);
    } catch (err) {
        console.error("Profile Load Error", err);
    }
}

async function updateProfile(e) {
    e.preventDefault();

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn ? btn.innerText : 'Save Changes';
    
    if(btn) { btn.disabled = true; btn.innerText = 'Saving...'; }

    const payload = { 
        first_name: document.getElementById('edit-fname')?.value.trim(), 
        last_name: document.getElementById('edit-lname')?.value.trim(), 
        email: document.getElementById('edit-email')?.value.trim() 
    };

    try {
        const updatedUser = await window.ApiService.patch('/customers/me/', payload);
        if(window.Toast) window.Toast.success('Profile Updated Successfully');
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(updatedUser));
        renderUserInfo(updatedUser);
        closeProfileModal();
    } catch (err) {
        console.error('Update Error:', err);
        let msg = err.message || 'Update failed';
        if (err.data && err.data.detail) msg = err.data.detail;
        if (typeof err.data === 'object' && !err.data.detail) {
            const firstKey = Object.keys(err.data)[0];
            msg = `${firstKey}: ${err.data[firstKey][0]}`;
        }
        if(window.Toast) window.Toast.error(msg);
    } finally {
        if(btn) { btn.disabled = false; btn.innerText = originalText; }
    }
}

function openEditModal() {
    const modal = document.getElementById('profile-modal');
    if (modal) { modal.classList.remove('d-none'); modal.style.display = 'flex'; }
}

window.closeProfileModal = function () {
    const modal = document.getElementById('profile-modal');
    if (modal) { modal.classList.add('d-none'); modal.style.display = 'none'; }
};

/* =========================
   STATS LOGIC
========================= */
async function loadStats() {
    try {
        const res = await window.ApiService.get('/orders/my/');
        const orders = res.results || res;

        const totalOrdersEl = document.getElementById('total-orders');
        if (totalOrdersEl) totalOrdersEl.innerText = orders.length;

        const totalSpent = orders.reduce((sum, o) => sum + Number(o.final_amount || o.total_amount || 0), 0);
        const totalSpentEl = document.getElementById('total-spent');
        if (totalSpentEl && window.Formatters) totalSpentEl.innerText = window.Formatters.currency(totalSpent);

    } catch (err) { console.warn('Failed to load stats', err); }
}

/* =========================
   RECENT ORDERS (DASHBOARD)
========================= */
const getStatusConfig = (status) => {
    const s = (status || 'PENDING').toLowerCase();
    if (s === 'delivered') return { class: 'delivered', icon: 'fa-check-circle', text: 'Delivered' };
    if (s === 'cancelled') return { class: 'cancelled', icon: 'fa-times-circle', text: 'Cancelled' };
    if (s === 'shipped' || s === 'out_for_delivery') return { class: 'shipped', icon: 'fa-truck', text: s.replace(/_/g, ' ') };
    return { class: 'processing', icon: 'fa-box-open', text: s.replace(/_/g, ' ') };
};

async function loadRecentOrders() {
    const container = document.getElementById('recent-orders-list');
    if (!container) return;

    try {
        const res = await window.ApiService.get('/orders/my/?page_size=3');
        const orders = res.results || res;

        if (!orders || orders.length === 0) {
            container.innerHTML = `
                <div class="empty-state text-center py-4" style="background: #f8fafc; border-radius: 12px;">
                    <i class="fas fa-shopping-bag text-muted mb-2" style="font-size: 2rem;"></i>
                    <p class="text-muted mb-0">No orders placed yet.</p>
                </div>`;
            return;
        }

        container.innerHTML = orders.map(renderOrderCardPro).join('');
    } catch (e) {
        console.error("Order Load Error", e);
        container.innerHTML = '<p class="text-danger text-center">Failed to load recent orders.</p>';
    }
}

// Premium Order Card Generator
function renderOrderCardPro(order) {
    const statusConfig = getStatusConfig(order.status);
    const date = new Date(order.created_at).toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
    
    const itemsCount = order.item_count || (order.items ? order.items.length : 1);
    const totalAmount = order.final_amount || order.total_amount || 0;
    const isCancelledClass = statusConfig.class === 'cancelled' ? 'is-cancelled' : '';

    let partialCancelBadge = '';
    if (order.status !== 'cancelled' && order.items) {
        const hasCancelledItems = order.items.some(item => item.status === 'cancelled' || item.is_cancelled);
        if (hasCancelledItems) {
            partialCancelBadge = `<div style="font-size: 0.75rem; color: #9a3412; background: #ffedd5; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 4px;"><i class="fas fa-exclamation-triangle"></i> Partial items cancelled</div>`;
        }
    }

    return `
        <div class="order-card-pro ${isCancelledClass}">
            <div class="order-card-header">
                <div class="order-id-pro">
                    <i class="fas fa-shopping-bag text-primary"></i> 
                    Order #${order.id || order.order_id}
                </div>
                <div class="status-badge ${statusConfig.class}">
                    <i class="fas ${statusConfig.icon}"></i> ${statusConfig.text}
                </div>
            </div>
            <div class="order-card-body">
                <div class="order-details-summary">
                    <span class="order-date-pro"><i class="far fa-clock"></i> ${date}</span>
                    <span class="order-items-count">${itemsCount} Item(s)</span>
                    ${partialCancelBadge}
                </div>
                <div class="order-total-pro">
                    ${window.Formatters ? window.Formatters.currency(totalAmount) : `₹${parseFloat(totalAmount).toFixed(2)}`}
                </div>
            </div>
            <div class="order-card-footer">
                <button class="btn-view-details" onclick="window.location.href='/order_detail.html?id=${order.id}'">
                    View Details <i class="fas fa-chevron-right" style="font-size:0.8em; margin-left:4px;"></i>
                </button>
            </div>
        </div>
    `;
}