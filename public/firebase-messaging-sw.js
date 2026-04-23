importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyCBAIMVBmnnCA_nAV1KmTrrkmaB65XSOAA",
  authDomain: "style-matcher-9480d.firebaseapp.com",
  projectId: "style-matcher-9480d",
  storageBucket: "style-matcher-9480d.firebasestorage.app",
  messagingSenderId: "405095915331",
  appId: "1:405095915331:web:72b14637a116eb3ac259f6"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message ', payload);
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/icon-512x512.png'
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});
