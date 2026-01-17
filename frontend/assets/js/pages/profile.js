// frontend/assets/js/pages/profile.js

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

/* =========================
   EVENT BINDINGS
========================= */
function bindEvents() {
    // 1. Profile Update Form Submit
    const profileForm = document.getElementById('profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', updateProfile);
    }

    // 2. Edit Profile Button Click
    const editBtn = document.getElementById('edit-profile-btn');
    if (editBtn) {
        editBtn.addEventListener('click', openEditModal);
    }

    // 3. Logout Button Click
    const logoutBtn = document.getElementById('logout-btn-page');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            if (typeof window.logout === 'function') {
                window.logout();
            } else {
                // Fallback logout if window.logout is not defined
                localStorage.clear();
                window.location.href = 'auth.html';
            }
        });
    }

    // 4. Close Modal Buttons
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

    // --- 1. Name Display ---
    const nameEl = document.getElementById('user-name');
    if (nameEl) {
        let displayName = '';
        
        if (user.first_name) {
            displayName = user.first_name;
            if (user.last_name) displayName += ` ${user.last_name}`;
        } else {
            // Default agar name na ho
            displayName = 'User'; 
        }
        
        nameEl.innerText = displayName;
    }

    // --- 2. Phone Display (Updated Logic) ---
    const phoneEl = document.getElementById('user-phone');
    if (phoneEl) {
        // Backend kabhi 'phone' bhejta hai, kabhi 'mobile'
        const phoneValue = user.phone || user.mobile || '';
        
        if (phoneValue) {
            phoneEl.innerText = phoneValue;
            phoneEl.style.color = '#333'; // Make it visible
        } else {
            phoneEl.innerText = 'Add Phone Number';
            phoneEl.style.color = '#999';
        }
    }

    // --- 3. Avatar/Greeting ---
    const greeting = document.getElementById('user-greeting');
    if (greeting) greeting.innerText = user.first_name || 'User';
    
    const avatarEl = document.querySelector('.avatar-circle');
    if (avatarEl) {
        // Pehla letter uthayein (e.g., 'R' for Rahul)
        const initial = user.first_name ? user.first_name.charAt(0).toUpperCase() : 'U';
        avatarEl.innerText = initial;
    }

    // --- 4. Pre-fill Edit Modal Inputs ---
    const editFname = document.getElementById('edit-fname'); 
    if (editFname) editFname.value = user.first_name || '';

    const editLname = document.getElementById('edit-lname');
    if (editLname) editLname.value = user.last_name || '';

    const editEmail = document.getElementById('edit-email'); 
    if (editEmail) editEmail.value = user.email || '';
}

/* =========================
   API: LOAD PROFILE
========================= */
async function loadProfile() {
    try {
        // Fetch fresh data from backend
        // Note: '/customers/me/' is standard for customer profiles
        const user = await window.ApiService.get('/customers/me/');
        
        // Update LocalStorage and UI
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));
        renderUserInfo(user);
    } catch (err) {
        console.error("Profile Load Error", err);
        // Error aane par hum kuch nahi karte, kyunki purana data already dikh raha hai
    }
}

/* =========================
   API: UPDATE PROFILE
========================= */
async function updateProfile(e) {
    e.preventDefault();

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn ? btn.innerText : 'Save Changes';
    
    if(btn) {
        btn.disabled = true;
        btn.innerText = 'Saving...';
    }

    // Get values from inputs
    const first_name = document.getElementById('edit-fname')?.value.trim();
    const last_name = document.getElementById('edit-lname')?.value.trim();
    const email = document.getElementById('edit-email')?.value.trim();

    const payload = { 
        first_name: first_name, 
        last_name: last_name, 
        email: email 
    };

    try {
        // Send PATCH request to update
        const updatedUser = await window.ApiService.patch('/customers/me/', payload);
        
        window.Toast.success('Profile Updated Successfully');
        
        // Update Local Storage & UI immediately
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(updatedUser));
        renderUserInfo(updatedUser);
        
        closeProfileModal();

    } catch (err) {
        console.error('Update Error:', err);
        let msg = err.message || 'Update failed';
        if (err.data && err.data.detail) msg = err.data.detail;
        
        // Sometimes backend errors are in object format {email: ["Invalid email"]}
        if (typeof err.data === 'object' && !err.data.detail) {
            const firstKey = Object.keys(err.data)[0];
            msg = `${firstKey}: ${err.data[firstKey][0]}`;
        }
        
        window.Toast.error(msg);
    } finally {
        if(btn) {
            btn.disabled = false;
            btn.innerText = originalText;
        }
    }
}

/* =========================
   MODAL UTILS
========================= */
function openEditModal() {
    const modal = document.getElementById('profile-modal');
    if (modal) {
        modal.classList.remove('d-none');
        modal.style.display = 'flex'; // Flex for centering
    }
}

window.closeProfileModal = function () {
    const modal = document.getElementById('profile-modal');
    if (modal) {
        modal.classList.add('d-none');
        modal.style.display = 'none';
    }
};

/* =========================
   STATS LOGIC
========================= */
async function loadStats() {
    try {
        const res = await window.ApiService.get('/orders/my/');
        const orders = res.results || res; // Handle pagination structure

        // 1. Total Orders
        const totalOrdersEl = document.getElementById('total-orders');
        if (totalOrdersEl) totalOrdersEl.innerText = orders.length;

        // 2. Total Spent
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
        const res = await window.ApiService.get('/orders/my/?page_size=3');
        const orders = res.results || res;

        if (!orders || orders.length === 0) {
            container.innerHTML = '<p class="text-muted text-center py-3">No orders placed yet.</p>';
            return;
        }

        container.innerHTML = orders.map(renderOrderCard).join('');
    } catch (e) {
        console.error("Order Load Error", e);
        container.innerHTML = '<p class="text-danger text-center">Failed to load recent orders.</p>';
    }
}

function renderOrderCard(order) {
    const dateStr = new Date(order.created_at).toLocaleDateString();
    const amount = order.final_amount || order.total_amount || 0;
    const status = order.status || 'Pending';
    
    // Status Badge Color Logic
    let badgeClass = 'badge-secondary';
    const s = status.toLowerCase();
    
    if (s === 'delivered') badgeClass = 'badge-success';
    else if (s === 'cancelled') badgeClass = 'badge-danger';
    else if (s === 'confirmed' || s === 'processing') badgeClass = 'badge-info';
    else if (s === 'shipped') badgeClass = 'badge-primary';

    return `
        <div class="order-card p-3 mb-2 bg-white rounded shadow-sm" 
             onclick="window.location.href='order_detail.html?id=${order.id}'" 
             style="cursor:pointer; border:1px solid #eee; transition: all 0.2s;">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong class="text-dark" style="font-size: 1rem;">Order #${order.id}</strong>
                    <p class="text-muted small mb-0 mt-1">
                        <i class="far fa-calendar-alt"></i> ${dateStr}
                    </p>
                </div>
                <div class="text-right">
                    <span class="badge ${badgeClass} mb-1" style="font-size: 0.75rem; padding: 4px 8px;">${status}</span>
                    <div class="font-weight-bold text-primary mt-1">
                        ${window.Formatters.currency(amount)}
                    </div>
                </div>
            </div>
        </div>
    `;
}