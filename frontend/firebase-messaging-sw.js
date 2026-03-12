// firebase-messaging-sw.js
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

const firebaseConfig = {
  apiKey: "AIzaSyBLN2izNbTgaG6K-9zblxVIx70TL8QzVbo",
  authDomain: "quickdash-2dd12.firebaseapp.com",
  projectId: "quickdash-2dd12",
  storageBucket: "quickdash-2dd12.firebasestorage.app",
  messagingSenderId: "808946416778",
  appId: "1:808946416778:web:c59376f6d73b3937bf4173",
  measurementId: "G-JFB92V2QG3"
};

// Initialize Firebase App in Service Worker
firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Background message handler
messaging.onBackgroundMessage(function(payload) {
    console.log('[firebase-messaging-sw.js] Received full payload: ', JSON.stringify(payload));
    
    // Safety check
    if (payload.notification) {
        console.log('Notification block detected, letting browser handle it.');
        return;
    }

    // 🔴 BUG FIX YAHAN HAI: 
    // Kabhi kabhi 'data' sidha payload mein hota hai, aur kabhi payload.data mein.
    // Hum dono check karenge.
    const messageData = payload.data || payload; 

    // Ab title aur body nikalenge (Pehle object mein check, nahi toh default)
    const notificationTitle = messageData.title || "QuickDash Alert!";
    const notificationBody = messageData.body || messageData.message || "New order update!";

    console.log('[firebase-messaging-sw.js] Showing notification -> Title:', notificationTitle, 'Body:', notificationBody);

    const notificationOptions = {
        body: notificationBody,
        icon: '/assets/images/logo.png', // Aapka QuickDash logo
        data: messageData // Pura data save kar lo taaki click par kaam aaye
    };

    self.registration.showNotification(notificationTitle, notificationOptions);
});

