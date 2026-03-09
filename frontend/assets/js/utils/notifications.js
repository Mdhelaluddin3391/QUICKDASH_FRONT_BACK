document.addEventListener("DOMContentLoaded", () => {
    // HTML se popup aur buttons ko select karna
    const modal = document.getElementById('custom-notification-modal');
    const btnAccept = document.getElementById('btn-accept-notify');
    const btnReject = document.getElementById('btn-reject-notify');

    // Agar kisi page par modal nahi hai, toh error na aaye isliye ye check
    if (!modal || !btnAccept || !btnReject) return;

    // Function: Check karna ki popup dikhana hai ya nahi
    function checkNotificationPermission() {
        if (!("Notification" in window)) {
            console.log("This browser does not support desktop notification");
            return;
        }

        // Agar user ne abhi tak yes/no nahi kiya, aur session mein 'dismiss' save nahi hai
        if (Notification.permission === "default" && !sessionStorage.getItem('notificationModalDismissed')) {
            setTimeout(() => {
                modal.classList.remove('hidden');
            }, 3000); // 3 second baad popup aayega
        }
    }

    // Reject (Not Now) Button Logic
    btnReject.addEventListener('click', () => {
        modal.classList.add('hidden');
        sessionStorage.setItem('notificationModalDismissed', 'true');
    });

    // Accept (Yes, Notify Me) Button Logic
    btnAccept.addEventListener('click', async () => {
        modal.classList.add('hidden'); // Pehle apna custom modal band karo
        
        try {
            // Asli browser popup trigger hoga
            const permission = await Notification.requestPermission();
            
            if (permission === "granted") {
                console.log("Notification permission granted.");
                
                // 1. Firebase se VAPID key ke sath Token maangna
                const currentToken = await firebase.messaging().getToken({ 
                    vapidKey: 'V1oP5rw8TIseT0-u-mLFdfRYY1BPvHYmIx8hcUFDh8A' // <--- Yahan daal di hai
                });

                if (currentToken) {
                    console.log("FCM Token generated:", currentToken);
                    
                    // 2. Token ko aapke Django Backend API pe bhejna
                    fetch('/api/notifications/fcm/subscribe/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ token: currentToken })
                    })
                    .then(response => response.json())
                    .then(data => {
                        console.log("Django Server Response:", data);
                        // Optional: showToast("Notifications enabled!", "success");
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

    // Code ko start karna
    checkNotificationPermission();
});