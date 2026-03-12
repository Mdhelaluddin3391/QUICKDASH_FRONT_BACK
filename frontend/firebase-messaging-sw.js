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
// Background message handler
messaging.onBackgroundMessage(function(payload) {
    console.log('[firebase-messaging-sw.js] Received background message ', payload);
    
    // Safety check: Agar galti se backend notification bhej de, toh manual code rok do
    if (payload.notification) {
        console.log('Notification block detected, letting browser handle it to avoid duplicates.');
        return;
    }

    // Ab payload.data se title aur body nikalenge
    const notificationTitle = payload.data?.title || "QuickDash Alert!";
    const notificationOptions = {
        body: payload.data?.body || "New order update!",
        icon: '/assets/images/logo.png', // Aapka QuickDash logo
        data: payload.data
    };

    self.registration.showNotification(notificationTitle, notificationOptions);
});