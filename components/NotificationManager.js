"use client";

import { useEffect } from "react";
import { app } from "../lib/firebase";
import { getMessaging, getToken, onMessage, isSupported } from "firebase/messaging";

export default function NotificationManager() {
  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) return;

    const setupNotifications = async () => {
      // 🛡️ Guard: Check if the browser supports FCM (required for Next.js/Safari/Localhost)
      const supported = await isSupported();
      if (!supported) {
        console.warn("⚠️ [FCM] Push notifications are not supported in this browser.");
        return;
      }

      const messaging = getMessaging(app);

      try {
        const permission = await Notification.requestPermission();
        if (permission === "granted") {
          const token = await getToken(messaging, {
            vapidKey: process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY
          });
          
          if (token) {
            console.log("🔔 [FCM] Token generated:", token);
            
            try {
              const hostname = window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname;
              const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
              await fetch(`${baseUrl}/api/notifications/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, topic: 'all_users' })
              });
              console.log("✅ [FCM] Token registered with backend.");
            } catch (regError) {
              console.warn("⚠️ [FCM] Token registration failed:", regError);
            }
          }
        }
      } catch (error) {
        console.error("⚠️ [FCM] Notification setup failed:", error);
      }

      // Foreground message handler
      const unsubscribe = onMessage(messaging, (payload) => {
        console.log("📨 [FCM] Foreground message received:", payload);
        const { title, body } = payload.notification;
        new Notification(title, { body });
      });

      return unsubscribe;
    };

    const cleanupPromise = setupNotifications();

    return () => {
      cleanupPromise.then(unsubscribe => {
        if (typeof unsubscribe === 'function') unsubscribe();
      });
    };
  }, []);

  return null;
}
