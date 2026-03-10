document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById('custom-notification-modal');
    const btnAccept = document.getElementById('btn-accept-notify');
    const btnReject = document.getElementById('btn-reject-notify');

    if (!modal || !btnAccept || !btnReject) return;

    function checkNotificationPermission() {
        if (!("Notification" in window)) {
            console.log("This browser does not support desktop notifications.");
            return;
        }

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
                
                // 1. Get Token from Firebase
                const currentToken = await firebase.messaging().getToken({ 
                    vapidKey: 'V1oP5rw8TIseT0-u-mLFdfRYY1BPvHYmIx8hcUFDh8A' // Your VAPID key
                });

                if (currentToken) {
                    console.log("FCM Token generated:", currentToken);
                    
                    // 2. Get User's Auth Token (Change 'access_token' if you saved it under a different name in localStorage)
                    const accessToken = localStorage.getItem('access_token'); 
                    
                    // 3. Send token to Django API
                    fetch(`${window.env.API_BASE_URL}/notifications/fcm/subscribe/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            // Only add Authorization header if the user is actually logged in
                            ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
                        },
                        // Ensure the key matches request.data.get('token') in views.py
                        body: JSON.stringify({ token: currentToken }) 
                    })
                    .then(response => response.json())
                    .then(data => {
                        console.log("Django Server Response:", data);
                        // Optional: Show a success toast here
                    })
                    .catch(error => console.error("Error sending token to Django:", error));

                } else {
                    console.log("No registration token available.");
                }

            } else {
                console.log("Permission denied by user.");
            }
        } catch (error) {
            console.error("Error asking for permission:", error);
        }
    });

    checkNotificationPermission();

    // =========================================================
    // UPDATE: Foreground Notification Listener (Website open hone par)
    // =========================================================
    if ('Notification' in window && navigator.serviceWorker) {
        firebase.messaging().onMessage((payload) => {
            console.log('[Foreground] Message received. ', payload);
            
            const title = payload.notification?.title || "New Alert!";
            const body = payload.notification?.body || "You have a new notification.";
            
            // Browser notification show karna
            new Notification(title, {
                body: body,
                icon: '/assets/images/logo.png', // Apna QuickDash logo yahan set karein
            });
            
            // Note: Agar aapke project mein custom Toast Alert system hai, 
            // toh aap use bhi yahan call kar sakte hain. Example: showToast(title, body)
        });
    }
});