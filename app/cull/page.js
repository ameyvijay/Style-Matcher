"use client";

import { useState, useEffect } from "react";
import { db, auth } from "../../lib/firebase";
import { collection, query, where, limit, onSnapshot, doc, updateDoc, increment } from "firebase/firestore";
import SwipeCard from "../../components/SwipeCard";
import AuthGuard from "../../components/AuthGuard";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, BarChart2, History, LogOut, AlertCircle } from "lucide-react";
import { signOut } from "firebase/auth";
import Link from "next/link";
import styles from "./cull.module.css";

export default function CullPage() {
  const [photos, setPhotos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reviewQueue, setReviewQueue] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchQueue = async () => {
      try {
        const response = await fetch("/api/batch-queue");
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("Manifest Not Found");
          }
          throw new Error("Failed to load batch queue");
        }
        const data = await response.json();
        setReviewQueue(data);
        setPhotos(data.photos || []);
        setLoading(false);
      } catch (err) {
        console.error("Manifest load error:", err);
        setError(err.message);
        setLoading(false);
      }
    };

    fetchQueue();

    /* Commenting out original Firestore listener for SSE Elimination
    const q = query(
      collection(db, "photos"),
      where("status", "==", "pending"),
      limit(20)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const photoData = snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
      }));
      setPhotos(photoData.sort((a, b) => b.score - a.score));
      setLoading(false);
    });

    return () => unsubscribe();
    */
  }, []);

  const handleSwipe = async (photoId, batchId, status) => {
    try {
      // 1. Update Photo Status
      const photoRef = doc(db, "photos", photoId);
      await updateDoc(photoRef, {
        status: status,
        user_id: "local_testing_user",
        decided_at: new Date().toISOString()
      });

      // 2. Increment Batch Progress
      const batchRef = doc(db, "batches", batchId);
      await updateDoc(batchRef, {
        processed_count: increment(1)
      });

      // Local state will update via onSnapshot listener
    } catch (error) {
      console.error("Error updating decision:", error);
    }
  };

  return (
    <AuthGuard>
      <main className={styles.cullMain}>
        {/* Navigation Header */}
        <header className={styles.cullHeader}>
          <div className={styles.cullHeaderLeft}>
            <div className={styles.cullHeaderIcon}>
              <Sparkles size={20} color="white" />
            </div>
            <span className={styles.cullHeaderTitle}>RLHF CULL</span>
          </div>
          
          <div className={styles.cullHeaderRight}>
            <Link href="/qa" className={styles.headerBtn}>
              <History size={20} />
            </Link>
            <Link href="/dashboard" className={styles.headerBtn}>
              <BarChart2 size={20} />
            </Link>
            <button 
              onClick={() => signOut(auth)}
              className={`${styles.headerBtn} ${styles.logoutBtn}`}
            >
              <LogOut size={20} />
            </button>
          </div>
        </header>

        {/* Swipe Area */}
        <div className={styles.swipeArea}>
          {error === "Manifest Not Found" ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyStateIcon} style={{ color: "#f87171" }}>
                <AlertCircle size={48} />
              </div>
              <h2 className={styles.emptyStateTitle}>Manifest Not Found</h2>
              <p className={styles.emptyStateDesc}>
                The batch_queue.json is missing. Please restart the processing engine.
              </p>
            </div>
          ) : (
            <AnimatePresence>
              {photos.length > 0 ? (
                photos.slice(0, 3).reverse().map((photo, index) => (
                  <SwipeCard 
                    key={photo.id}
                    photo={photo}
                    onSwipe={(status) => handleSwipe(photo.id, photo.batch_id, status)}
                  />
                ))
              ) : (
                !loading && (
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className={styles.emptyState}
                  >
                    <div className={styles.emptyStateIcon}>
                      <Sparkles size={48} />
                    </div>
                    <h2 className={styles.emptyStateTitle}>Queue Clear!</h2>
                    <p className={styles.emptyStateDesc}>
                      You've processed all pending photos. Great work!
                    </p>
                  </motion.div>
                )
              )}
            </AnimatePresence>
          )}
          
          {loading && (
            <div className={styles.loaderOverlay}>
              <motion.div 
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                className={styles.loaderSpinner}
              />
            </div>
          )}
        </div>

        {/* Hint Footer */}
        <footer className={styles.cullFooter}>
          <div className={styles.cullFooterHints}>
            <div className={styles.hintItem}>
              <div className={`${styles.hintCircle} ${styles.hintCircleReject}`}>
                <span>L</span>
              </div>
              <span className={styles.hintText}>Reject</span>
            </div>
            <div className={styles.hintItem}>
              <div className={`${styles.hintCircle} ${styles.hintCircleAccept}`}>
                <span>R</span>
              </div>
              <span className={styles.hintText}>Accept</span>
            </div>
          </div>
          <p className={styles.footerRemaining}>
            {photos.length} photos remaining in local stack
          </p>
        </footer>
      </main>
    </AuthGuard>
  );
}
