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
    console.log('[firebase-messaging-sw.js] Received background message ', payload);
    
    const notificationTitle = payload.notification?.title || "QuickDash Alert!";
    const notificationOptions = {
        body: payload.notification?.body || "Aapke liye ek naya update hai!",
        icon: '/assets/images/logo.png', // Apna QuickDash logo yahan set karein
        data: payload.data
    };

    self.registration.showNotification(notificationTitle, notificationOptions);
});