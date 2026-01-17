// frontend/assets/js/pages/profile.js

document.addEventListener('DOMContentLoaded', initDashboard);

/* =========================
   INITIALIZATION
========================= */
async function initDashboard() {
    // Critical Security Check: Agar user login nahi hai, turant redirect karein
    if (!isAuthenticated()) {
        document.body.style.display = 'none'; // Content hide karein
        const loginUrl = window.APP_CONFIG?.ROUTES?.LOGIN || 'auth.html';
        window.location.replace(loginUrl);
        return;
    }

    // 1. LocalStorage se turant data dikhayein (Fast Experience)
    const storedUser = getStoredUser();
    if (storedUser && Object.keys(storedUser).length > 0) {
        renderUserInfo(storedUser);
    }

    // 2. Buttons aur Forms ke events connect karein
    bindEvents();

    // 3. Server se fresh data mangwayein
    try {
        await Promise.all([
            loadProfile(),      // Profile Info
            loadStats(),        // Total Orders/Spent
            loadRecentOrders()  // Recent List
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
    // Profile Update Form
    const profileForm = document.getElementById('profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', updateProfile);
    }

    // Edit Button
    const editBtn = document.getElementById('edit-profile-btn');
    if (editBtn) {
        editBtn.addEventListener('click', openEditModal);
    }

    // Logout Button
    const logoutBtn = document.getElementById('logout-btn-page');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', window.logout);
    }

    // Close Modal Logic
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
    // 1. Name Display
    const nameEl = document.getElementById('user-name');
    if (nameEl) {
        // Agar first_name hai toh dikhayein, nahi toh 'User'
        let displayName = user.first_name || 'User';
        if (user.last_name) displayName += ` ${user.last_name}`;
        nameEl.innerText = displayName;
    }

    // 2. Phone Display
    const phoneEl = document.getElementById('user-phone');
    if (phoneEl) {
        phoneEl.innerText = user.phone || 'No Phone Added';
    }

    // 3. Greeting
    const greeting = document.getElementById('user-greeting');
    if (greeting) greeting.innerText = user.first_name || 'User';

    // 4. Pre-fill Edit Form (Modal inputs)
    // Note: HTML mein inputs ke ID check kar lein
    
    // First Name
    const editFname = document.getElementById('edit-fname'); 
    if (editFname) editFname.value = user.first_name || '';

    // Last Name
    const editLname = document.getElementById('edit-lname');
    if (editLname) editLname.value = user.last_name || '';

    // Email
    const editEmail = document.getElementById('edit-email'); 
    // Agar alag ID hai (jaise 'p-email') toh fallback check
    const emailInput = editEmail || document.getElementById('p-email');
    if (emailInput) emailInput.value = user.email || '';
}

/* =========================
   API: LOAD PROFILE
========================= */
async function loadProfile() {
    try {
        // ✅ FIX: Correct Endpoint for Customer Profile
        // 'auth/profile/' galat tha, 'customers/me/' sahi hai backend ke hisab se
        const user = await window.ApiService.get('/customers/me/');
        
        // Save to LocalStorage & Render
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));
        renderUserInfo(user);
    } catch (err) {
        console.error("Profile Load Error", err);
    }
}

/* =========================
   API: UPDATE PROFILE
========================= */
async function updateProfile(e) {
    e.preventDefault();

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn ? btn.innerText : 'Save';
    if(btn) {
        btn.disabled = true;
        btn.innerText = 'Saving...';
    }

    // Data Collection from Form
    // Hum koshish karenge specific IDs se data lene ki, nahi toh form se
    let first_name = document.getElementById('edit-fname')?.value.trim();
    let last_name = document.getElementById('edit-lname')?.value.trim();
    let email = document.getElementById('edit-email')?.value.trim() || document.getElementById('p-email')?.value.trim();

    // Fallback: Agar user ne purana HTML use kiya hai jisme ek hi 'p-name' field hai
    if (!first_name) {
        const fullNameInput = document.getElementById('p-name');
        if (fullNameInput) {
            const parts = fullNameInput.value.trim().split(' ');
            first_name = parts[0];
            last_name = parts.slice(1).join(' ');
        }
    }

    const payload = { first_name, last_name, email };

    try {
        // ✅ FIX: Correct Endpoint for Update
        const updatedUser = await window.ApiService.patch('/customers/me/', payload);
        
        window.Toast.success('Profile Updated Successfully');
        
        // Update Local Storage & UI
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(updatedUser));
        renderUserInfo(updatedUser);
        closeProfileModal();

    } catch (err) {
        console.error(err);
        let msg = err.message || 'Update failed';
        if (err.data && err.data.detail) msg = err.data.detail;
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
        modal.style.display = 'flex'; // Ensure flex rendering
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
        // ✅ FIX: Correct Endpoint -> '/orders/my/' 
        const res = await window.ApiService.get('/orders/my/');
        const orders = res.results || res;

        // Update Total Orders Count
        const totalOrdersEl = document.getElementById('total-orders');
        if (totalOrdersEl) totalOrdersEl.innerText = orders.length;

        // Calculate Total Spent
        const totalSpent = orders.reduce(
            (sum, o) => sum + Number(o.final_amount || o.total_amount || 0),
            0
        );

        // Update Total Spent Amount
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
        // ✅ FIX: Correct Endpoint -> '/orders/my/'
        const res = await window.ApiService.get('/orders/my/?page_size=3');
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
    
    // Status Color Logic
    const status = order.status || 'Pending';
    let badgeClass = 'badge-secondary';
    if (status.toLowerCase() === 'delivered') badgeClass = 'badge-success';
    else if (status.toLowerCase() === 'cancelled') badgeClass = 'badge-danger';
    else if (status.toLowerCase() === 'confirmed') badgeClass = 'badge-info';

    return `
        <div class="order-card p-3 mb-2 bg-white rounded shadow-sm" 
             onclick="window.location.href='order_detail.html?id=${order.id}'" 
             style="cursor:pointer; border:1px solid #eee;">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong class="text-dark">Order #${order.id}</strong>
                    <p class="text-muted small mb-0"><i class="far fa-calendar-alt"></i> ${dateStr}</p>
                </div>
                <div class="text-right">
                    <span class="badge ${badgeClass} mb-1">${status}</span>
                    <div class="font-weight-bold text-primary">
                        ${window.Formatters.currency(amount)}
                    </div>
                </div>
            </div>
        </div>
    `;
}