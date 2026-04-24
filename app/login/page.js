"use client";

import { useState, useEffect } from "react";
import { auth, googleProvider } from "../../lib/firebase";
import { onAuthStateChanged, signInWithPopup } from "firebase/auth";
import { useRouter } from "next/navigation";
import { Sparkles, LogIn } from "lucide-react";
import { motion } from "framer-motion";
import styles from "./login.module.css";

export default function LoginPage() {
  const router = useRouter();

  const handleLogin = async () => {
    try {
      await signInWithPopup(auth, googleProvider);
    } catch (error) {
      console.error("Login failed:", error);
      if (error.code === 'auth/unauthorized-domain') {
        alert("This domain is not authorized in Firebase Console. Please add 'localhost' to Authorized Domains.");
      }
    }
  };

  useEffect(() => {
    const checkUser = onAuthStateChanged(auth, (user) => {
      if (user) {
        router.push("/dashboard");
      }
    });
    return () => checkUser();
  }, [router]);

  return (
    <main className={styles.main}>
      {/* Background Blobs */}
      <div className={styles.bgWrapper}>
        <div className={`${styles.blob1} ${styles.blobPulse}`}></div>
        <div className={`${styles.blob2} ${styles.blobPulse}`}></div>
      </div>

      <motion.div 
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.8 }}
        className={styles.card}
      >
        <div className={styles.iconWrapper}>
          <div className={styles.iconInner}>
            <Sparkles size={40} />
          </div>
        </div>

        <h1 className={styles.title}>Style Matcher</h1>
        <p className={styles.desc}>
          The ultimate engine for pro photo culling and RLHF feedback.
        </p>

        <button 
          onClick={handleLogin}
          className={styles.loginBtn}
        >
          <LogIn size={20} />
          Continue with Google
        </button>

        {process.env.NODE_ENV === 'development' && (
          <button 
            onClick={() => router.push("/cull")}
            style={{ 
              marginTop: '1rem', 
              background: 'transparent', 
              border: '1px dashed rgba(255,255,255,0.2)', 
              color: 'rgba(255,255,255,0.5)',
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              fontSize: '0.8rem',
              cursor: 'pointer'
            }}
          >
            🚧 Dev Bypass (Local Only)
          </button>
        )}

        <p className={styles.footerText}>
          Powered by Antigravity v2.1
        </p>

        {process.env.NODE_ENV === 'development' && (
          <div style={{
            marginTop: '2rem',
            padding: '1rem',
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '12px',
            border: '1px solid rgba(255,255,255,0.08)',
            fontSize: '0.75rem',
            color: 'rgba(255,255,255,0.4)',
            maxWidth: '280px',
            textAlign: 'center'
          }}>
            <p style={{ marginBottom: '0.5rem', fontWeight: '600' }}>📱 Mobile Connection Tip</p>
            To use the M4 compute engine from your phone, ensure your mobile is on the same WiFi and set <code style={{ color: '#60a5fa' }}>NEXT_PUBLIC_API_URL</code> to your Mac's local IP (e.g. 192.168.x.x).
          </div>
        )}
      </motion.div>
    </main>
  );
}
