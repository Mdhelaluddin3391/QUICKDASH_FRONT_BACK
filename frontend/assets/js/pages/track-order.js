async function loadMapsScript() {
    if (window.AppConfigService && !window.AppConfigService.isLoaded) {
        try { await window.AppConfigService.load(); } catch (e) { }
    }

    const key = window.APP_CONFIG.GOOGLE_MAPS_KEY;
    const placeholder = document.getElementById('map-placeholder');

    if (!key || key.includes('REPLACE') || key.length < 10) {
        placeholder.innerHTML = `
            <div class="text-center p-4">
                <i class="fas fa-map-marked-alt fa-3x mb-3 text-muted"></i>
                <h4>Map Unavailable</h4>
                <p class="small text-muted">Live tracking is active, but the map view is disabled.</p>
            </div>`;
        return;
    }

    if (document.getElementById('gmaps-script')) return;

    const script = document.createElement('script');
    script.id = 'gmaps-script';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${key}&callback=initMap`;
    script.async = true;
    script.defer = true;
    script.onerror = () => {
        placeholder.innerHTML = '<p>Map loading failed (Network Error)</p>';
    };
    document.body.appendChild(script);
}

let map, marker, riderMarker, orderId, socket;
let reconnectInterval = 1000;

window.initMap = function () {
    try {
        const mapEl = document.getElementById('map');
        if (!mapEl) return;

        map = new google.maps.Map(mapEl, {
            center: { lat: 12.9716, lng: 77.5946 },
            zoom: 13,
            disableDefaultUI: true
        });
        marker = new google.maps.Marker({ map: map, title: "Destination" });
        riderMarker = new google.maps.Marker({
            map: map,
            icon: 'https://cdn-icons-png.flaticon.com/32/3063/3063823.png',
            title: "Rider"
        });
    } catch (e) {
        console.error("Map Init Error:", e);
    }
};

document.addEventListener('DOMContentLoaded', async () => {
    orderId = new URLSearchParams(window.location.search).get('id');
    if (!orderId) return window.location.href = './orders.html';

    document.getElementById('t-id').innerText = `Order #${orderId}`;

    await loadMapsScript();

    fetchOrderDetails();
    connectTrackingSocket();
});

async function fetchOrderDetails() {
    try {
        const order = await ApiService.get(`/orders/${orderId}/`);
        updateTimeline(order.status);

        if (order.delivery_address_json && typeof map !== 'undefined') {
            const pos = {
                lat: parseFloat(order.delivery_address_json.lat),
                lng: parseFloat(order.delivery_address_json.lng)
            };
            marker.setPosition(pos);
            map.panTo(pos);
        }

        if (order.delivery && order.delivery.rider && order.delivery.rider.user) {
            document.getElementById('rider-info').classList.remove('d-none');
            document.getElementById('r-name').innerText = order.delivery.rider.user.first_name || 'Rider';
            document.getElementById('r-phone').href = `tel:${order.delivery.rider.user.phone}`;
        }
    } catch (e) { console.error("Fetch error", e); }
}

function updateTimeline(status) {
    document.querySelectorAll('.timeline-step').forEach(el => el.classList.remove('active'));
    const map = {
        'created': [],
        'confirmed': ['step-confirmed'],
        'picking': ['step-confirmed'],
        'packed': ['step-confirmed', 'step-packed'],
        'out_for_delivery': ['step-confirmed', 'step-packed', 'step-dispatched'],
        'delivered': ['step-confirmed', 'step-packed', 'step-dispatched', 'step-delivered']
    };
    (map[status.toLowerCase()] || []).forEach(id => document.getElementById(id).classList.add('active'));
}

async function connectTrackingSocket(retryCount = 0) {
    try {
        const res = await ApiService.post('/auth/ws/ticket/');
        if (!res.ticket) throw new Error("No ticket received");

        const ticket = res.ticket;
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsUrl = `${protocol}://${window.location.host}/ws/tracking/${orderId}/${ticket}/`;

        socket = new WebSocket(wsUrl);
        reconnectInterval = 1000;

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.status) updateTimeline(data.status);
                if (data.rider_location && riderMarker) {
                    riderMarker.setPosition({
                        lat: parseFloat(data.rider_location.lat),
                        lng: parseFloat(data.rider_location.lng)
                    });
                }
            } catch (e) { console.error("WS Message Error:", e); }
        };

        socket.onerror = () => {
            console.error("WebSocket Error");
        };

        socket.onclose = () => {
            if (retryCount < 5) {
                setTimeout(() => connectTrackingSocket(retryCount + 1), reconnectInterval);
                reconnectInterval = Math.min(reconnectInterval * 1.5, 30000);
            }
        };
    } catch (e) {
        console.error("WS Connection Failed:", e);
        if (retryCount < 5) {
            setTimeout(() => connectTrackingSocket(retryCount + 1), reconnectInterval);
            reconnectInterval = Math.min(reconnectInterval * 1.5, 30000);
        }
    }
}
