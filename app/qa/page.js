"use client";

import { useState, useEffect } from "react";
import { db } from "../../lib/firebase";
import { collection, query, where, onSnapshot, doc, updateDoc, increment } from "firebase/firestore";
import AuthGuard from "../../components/AuthGuard";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, RotateCcw, Check, Trash2, LayoutGrid, List } from "lucide-react";
import Link from "next/link";
import styles from "./qa.module.css";

export default function QAPage() {
  const [rejectedPhotos, setRejectedPhotos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState("grid");

  useEffect(() => {
    const q = query(
      collection(db, "photos"),
      where("status", "==", "rejected")
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const photoData = snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
      }));
      setRejectedPhotos(photoData.sort((a, b) => b.score - a.score));
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const handleRescue = async (photoId, batchId) => {
    try {
      const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
      const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
      
      // 1. Tell backend to reverse decision (Syncs SQLite + ChromaDB)
      await fetch(`${baseUrl}/api/decision/reverse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_id: photoId, batch_id: batchId, action: "rescue" }),
      });

      // 2. Update Firestore for UI sync
      const photoRef = doc(db, "photos", photoId);
      await updateDoc(photoRef, {
        status: "accepted",
        rescued: true,
        rescued_at: new Date().toISOString()
      });
    } catch (error) {
      console.error("Rescue failed:", error);
    }
  };

  const handleReset = async (photoId, batchId) => {
    try {
      const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
      const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();

      // 1. Tell backend to reverse decision
      await fetch(`${baseUrl}/api/decision/reverse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_id: photoId, batch_id: batchId, action: "reset" }),
      });

      // 2. Reset Firestore photo status to 'pending'
      const photoRef = doc(db, "photos", photoId);
      await updateDoc(photoRef, {
        status: "pending"
      });
    } catch (error) {
      console.error("Reset failed:", error);
    }
  };

  return (
    <AuthGuard>
      <main className={styles.main}>
        {/* Header */}
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <Link href="/cull" className={styles.backBtn}>
              <ArrowLeft size={24} />
            </Link>
            <div>
              <h1 className={styles.title}>
                Second Chance Bin
              </h1>
              <p className={styles.subtitle}>
                QA Review: {rejectedPhotos.length} Photos
              </p>
            </div>
          </div>

          <div className={styles.viewToggle}>
            <button 
              onClick={() => setViewMode("grid")}
              className={`${styles.toggleBtn} ${viewMode === 'grid' ? styles.toggleBtnActive : styles.toggleBtnInactive}`}
            >
              <LayoutGrid size={20} />
            </button>
            <button 
              onClick={() => setViewMode("list")}
              className={`${styles.toggleBtn} ${viewMode === 'list' ? styles.toggleBtnActive : styles.toggleBtnInactive}`}
            >
              <List size={20} />
            </button>
          </div>
        </header>

        {/* Content */}
        <div className={styles.container}>
          {loading ? (
            <div className={styles.loaderWrap}>
              <motion.div 
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                className={styles.loaderSpinner}
              />
            </div>
          ) : rejectedPhotos.length > 0 ? (
            <div className={viewMode === 'grid' ? styles.gridMode : styles.listMode}>
              <AnimatePresence mode="popLayout">
                {rejectedPhotos.map((photo) => (
                  <motion.div
                    key={photo.id}
                    layout
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    className={`${styles.cardItem} ${viewMode === 'list' ? styles.cardItemList : ''}`}
                  >
                    {/* Thumbnail */}
                    <div className={`${styles.thumbWrap} ${viewMode === 'grid' ? styles.thumbGrid : styles.thumbList}`}>
                      <img 
                        src={photo.rlhf_url || photo.url} 
                        alt={photo.filename}
                        className={styles.thumbImg}
                      />
                      <div className={styles.actionsOverlay}>
                        <button 
                          onClick={() => handleRescue(photo.id, photo.batch_id)}
                          className={styles.actionBtnCheck}
                        >
                          <Check size={20} />
                        </button>
                        <button 
                          onClick={() => handleReset(photo.id, photo.batch_id)}
                          className={styles.actionBtnReset}
                        >
                          <RotateCcw size={20} />
                        </button>
                      </div>
                    </div>

                    {/* Metadata (List View) */}
                    {viewMode === 'list' && (
                      <div className={styles.listMeta}>
                        <h3 className={styles.metaTitle}>{photo.filename}</h3>
                        <p className={styles.metaSubtitle}>
                          Tier {photo.tier} | AI Score: {photo.score ? photo.score.toFixed(2) : 'N/A'}
                        </p>
                      </div>
                    )}

                    {viewMode === 'list' && (
                      <div className={styles.listActions}>
                         <button 
                          onClick={() => handleReset(photo.id, photo.batch_id)}
                          className={styles.listBtnReset}
                        >
                          <RotateCcw size={16} /> Reset
                        </button>
                        <button 
                          onClick={() => handleRescue(photo.id, photo.batch_id)}
                          className={styles.listBtnCheck}
                        >
                          <Check size={16} /> Rescue
                        </button>
                      </div>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          ) : (
            <div className={styles.emptyState}>
              <div className={styles.emptyIconWrap}>
                <div className={styles.emptyIconInner}>
                  <Trash2 size={64} />
                </div>
              </div>
              <h2 className={styles.emptyTitle}>The bin is empty</h2>
              <p className={styles.emptyDesc}>
                No rejected photos found. Either you&apos;re very happy with the model&apos;s choices, or you haven&apos;t started culling yet.
              </p>
              <Link href="/cull" className={`btn btn-primary ${styles.returnBtn}`}>
                Return to Culling
              </Link>
            </div>
          )}
        </div>
      </main>
    </AuthGuard>
  );
}
