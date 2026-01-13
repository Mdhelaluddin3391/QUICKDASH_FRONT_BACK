document.addEventListener('DOMContentLoaded', initDashboard);

/* =========================
   INITIALIZATION
========================= */
async function initDashboard() {
    if (!isAuthenticated()) {
        redirectToLogin();
        return;
    }

    const user = getStoredUser();
    renderUserInfo(user);

    bindEvents();

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
    return Boolean(localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN));
}

function redirectToLogin() {
    window.location.href = APP_CONFIG.ROUTES.LOGIN;
}

function getStoredUser() {
    return JSON.parse(
        localStorage.getItem(APP_CONFIG.STORAGE_KEYS.USER) || '{}'
    );
}

/* =========================
   EVENT BINDINGS
========================= */
function bindEvents() {
    document
        .getElementById('profile-form')
        .addEventListener('submit', updateProfile);

    document
        .getElementById('edit-profile-btn')
        .addEventListener('click', openEditModal);

    document
        .getElementById('logout-btn-page')
        .addEventListener('click', window.logout);
}

/* =========================
   USER INFO
========================= */
function renderUserInfo(user) {
    document.getElementById('user-name').innerText =
        user.first_name
            ? `${user.first_name} ${user.last_name || ''}`
            : 'QuickDash User';

    document.getElementById('user-phone').innerText = user.phone || '';

    // Pre-fill edit form
    document.getElementById('edit-fname').value = user.first_name || '';
    document.getElementById('edit-lname').value = user.last_name || '';
    document.getElementById('edit-email').value = user.email || '';
}

/* =========================
   STATS
========================= */
async function loadStats() {
    try {
        const res = await ApiService.get('/orders/my/');
        const orders = res.results || [];

        document.getElementById('total-orders').innerText = orders.length;

        const totalSpent = orders.reduce(
            (sum, o) => sum + Number(o.final_amount || 0),
            0
        );

        document.getElementById('total-spent').innerText =
            Formatters.currency(totalSpent);
    } catch (err) {
        console.warn('Failed to load stats', err);
    }
}

/* =========================
   RECENT ORDERS
========================= */
async function loadRecentOrders() {
    const container = document.getElementById('recent-orders-list');

    try {
        const res = await ApiService.get('/orders/my/?page_size=3');
        const orders = res.results || [];

        if (!orders.length) {
            container.innerHTML =
                '<p class="text-muted">No orders yet.</p>';
            return;
        }

        container.innerHTML = orders.map(renderOrderCard).join('');
    } catch {
        container.innerHTML =
            '<p class="text-danger">Failed to load orders</p>';
    }
}

function renderOrderCard(order) {
    return `
        <div class="order-card">
            <div>
                <strong>Order #${order.id.slice(0, 8).toUpperCase()}</strong>
                <p class="text-muted small">
                    ${Formatters.date(order.created_at)}
                </p>
            </div>
            <div class="text-right">
                <span class="status-badge status-${order.status.toLowerCase()}">
                    ${order.status}
                </span>
                <div class="mt-1 font-weight-bold">
                    ${Formatters.currency(order.final_amount)}
                </div>
            </div>
        </div>
    `;
}

/* =========================
   PROFILE
========================= */
function openEditModal() {
    document
        .getElementById('profile-modal')
        .classList.remove('d-none');
}

window.closeProfileModal = function () {
    document
        .getElementById('profile-modal')
        .classList.add('d-none');
};

async function loadProfile() {
    try {
        const user = await ApiService.get('/auth/profile/');

        document.getElementById('p-phone').value = user.phone;
        document.getElementById('p-name').value =
            `${user.first_name} ${user.last_name}`.trim();
        document.getElementById('p-email').value = user.email || '';

        const greeting = document.getElementById('user-greeting');
        if (greeting) greeting.innerText = user.first_name || 'User';
    } catch (err) {
        console.error(err);
        Toast.error('Failed to load profile');
    }
}

/* =========================
   UPDATE PROFILE
========================= */
async function updateProfile(e) {
    e.preventDefault();

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;

    btn.disabled = true;
    btn.innerText = 'Saving...';

    const [first_name, ...rest] =
        document.getElementById('p-name').value.trim().split(' ');

    const payload = {
        first_name,
        last_name: rest.join(' '),
        email: document.getElementById('p-email').value
    };

    try {
        await ApiService.patch('/auth/profile/', payload);
        Toast.success('Profile Updated');
        closeProfileModal();
    } catch (err) {
        Toast.error(err.message || 'Update failed');
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}
