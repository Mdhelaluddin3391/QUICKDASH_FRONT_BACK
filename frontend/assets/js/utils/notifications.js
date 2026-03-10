document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById('custom-notification-modal');
    const btnAccept = document.getElementById('btn-accept-notify');
    const btnReject = document.getElementById('btn-reject-notify');

    // 1. Safely check if Firebase is initialized and supported
    if (!window.firebase || !firebase.messaging || !firebase.messaging.isSupported()) {
        console.warn("Firebase Messaging is not supported or not initialized in this browser.");
        return;
    }

    const messaging = firebase.messaging();

    // 2. Separate logic to get the token and send it to Django
    // 2. Separate logic to get the token and send it to Django
    async function subscribeToPushNotifications() {
        try {
            console.log("Attempting to register Service Worker manually...");
            const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');

            // 🌟 THE FIX: Wait for the service worker to become fully ACTIVE
            console.log('Service Worker registered. Waiting for it to become active...');
            const readyRegistration = await navigator.serviceWorker.ready;
            console.log('Service Worker is now ACTIVE and READY!');

            // Pass the READY registration to Firebase
            const currentToken = await messaging.getToken({
                vapidKey: 'BHJ_VgQk4o1NwiKb-JtaF-md-OJsxeFLtItftNLQ8fBRBgPAlyIhWL6_sCUgMl4p8_jAn_r6Lgh-cu5Ld_KAVO0',
                serviceWorkerRegistration: readyRegistration
            });

            if (currentToken) {
                console.log("FCM Token generated:", currentToken);

                const tokenKey = window.APP_CONFIG?.STORAGE_KEYS?.TOKEN || 'access_token';
                const accessToken = localStorage.getItem(tokenKey);
                const apiBase = window.APP_CONFIG?.API_BASE_URL || "https://quickdash-front-back.onrender.com/api/v1";

                // Send token to Django API
                const response = await fetch(`${apiBase}/notifications/fcm/subscribe/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
                    },
                    body: JSON.stringify({ token: currentToken })
                });

                if (response.ok) {
                    const data = await response.json();
                    console.log("Django Server Response: Token saved successfully.", data);
                } else {
                    console.error("Failed to save token to server.", await response.text());
                }
            } else {
                console.log("No registration token available. Request permission to generate one.");
            }
        } catch (error) {
            console.error("An error occurred while retrieving token or sending to server:", error);
        }
    }

    // 3. Modal and Permission Logic
    if (modal && btnAccept && btnReject) {
        function checkNotificationPermission() {
            if (!("Notification" in window)) return;

            if (Notification.permission === "default" && !sessionStorage.getItem('notificationModalDismissed')) {
                setTimeout(() => {
                    modal.classList.remove('hidden');
                }, 3000);
            }
        }

        btnReject.addEventListener('click', () => {
            modal.classList.add('hidden');
            sessionStorage.setItem('notificationModalDismissed', 'true');
        });

        btnAccept.addEventListener('click', async () => {
            modal.classList.add('hidden');

            try {
                const permission = await Notification.requestPermission();
                if (permission === "granted") {
                    console.log("Notification permission granted.");
                    await subscribeToPushNotifications(); // Call the robust function
                } else {
                    console.log("Permission denied by user.");
                }
            } catch (error) {
                console.error("Error asking for permission:", error);
            }
        });

        checkNotificationPermission();
    }

    // If the user already granted permission previously, refresh the token silently
    if ("Notification" in window && Notification.permission === "granted") {
        subscribeToPushNotifications();
    }

    // =========================================================
    // UPDATE: Foreground Notification Listener (When website is open)
    // =========================================================
    messaging.onMessage((payload) => {
        console.log('[Foreground] Message received. ', payload);

        const title = payload.notification?.title || "New Alert!";
        const body = payload.notification?.body || "You have a new notification.";

        // Show Browser Notification if allowed
        if (Notification.permission === 'granted') {
            new Notification(title, {
                body: body,
                icon: '/assets/images/logo.png', // Fallback QuickDash Logo
            });
        }

        // Optional: Trigger QuickDash custom Toast if you have the Toast utility imported
        if (window.Toast && typeof window.Toast.show === 'function') {
            window.Toast.show(`${title}: ${body}`, 'info');
        }
    });
});