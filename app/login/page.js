"use client";

import { useState, useEffect } from "react";
import { auth, googleProvider, signInWithRedirect } from "../../lib/firebase";
import { onAuthStateChanged, getRedirectResult } from "firebase/auth";
import { useRouter } from "next/navigation";
import { Sparkles, LogIn } from "lucide-react";
import { motion } from "framer-motion";
import styles from "./login.module.css";

export default function LoginPage() {
  const router = useRouter();

  const handleLogin = () => {
    // Muted authentication for local testing
    router.push("/cull");
  };

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

        <p className={styles.footerText}>
          Powered by Antigravity v2.1
        </p>
      </motion.div>
    </main>
  );
}
