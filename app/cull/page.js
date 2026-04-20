"use client";

import { useState, useEffect, useCallback } from "react";
import { db, auth } from "../../lib/firebase";
import {
  collection,
  query,
  where,
  onSnapshot,
  doc,
  updateDoc,
  increment,
} from "firebase/firestore";
import SwipeCard from "../../components/SwipeCard";
import AuthGuard from "../../components/AuthGuard";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, BarChart2, History, LogOut, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { signOut } from "firebase/auth";
import Link from "next/link";
import { useImageCache } from "../../lib/useImageCache";
import { useSyncStatus } from "../../lib/useSyncStatus";

// ── Inline Styles ──────────────────────────────────────────────────────
const S = {
  main: {
    minHeight: "100dvh",
    background: "#050505",
    color: "#fff",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    paddingTop: "env(safe-area-inset-top, 0px)",
    paddingBottom: "env(safe-area-inset-bottom, 0px)",
    overflow: "hidden",
    position: "relative",
  },
  header: {
    width: "100%",
    maxWidth: "480px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "13px 16px",
    flexShrink: 0,
  },
  headerLeft: { display: "flex", alignItems: "center", gap: "10px" },
  headerIcon: {
    width: "34px", height: "34px", borderRadius: "10px",
    background: "linear-gradient(135deg, #3b82f6, #6366f1)",
    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
  },
  headerTitle: { fontWeight: "800", fontSize: "1rem", letterSpacing: "-0.02em" },
  headerBadge: {
    background: "rgba(96,165,250,0.14)", border: "1px solid rgba(96,165,250,0.24)",
    borderRadius: "100px", padding: "2px 8px", fontSize: "0.68rem", color: "#60a5fa", fontWeight: "700",
  },
  headerRight: { display: "flex", gap: "6px", alignItems: "center" },
  headerBtn: {
    width: "36px", height: "36px", borderRadius: "10px",
    background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.07)",
    color: "rgba(255,255,255,0.55)", display: "flex", alignItems: "center",
    justifyContent: "center", cursor: "pointer", textDecoration: "none",
  },
  swipeArea: {
    position: "relative", width: "100%", maxWidth: "420px",
    flex: 1, margin: "0 16px",
    maxHeight: "calc(100dvh - 130px)", minHeight: "0",
  },
  footer: {
    width: "100%", maxWidth: "420px",
    padding: "10px 16px 0", flexShrink: 0,
  },
  footerHints: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  hintGroup: { display: "flex", alignItems: "center", gap: "8px" },
  hintIcon: { width: "34px", height: "34px", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" },
  hintIconReject: { border: "1px solid rgba(248,113,113,0.35)", background: "rgba(248,113,113,0.07)", color: "#f87171" },
  hintIconAccept: { border: "1px solid rgba(16,185,129,0.35)", background: "rgba(16,185,129,0.07)", color: "#10b981" },
  hintLabel: { fontSize: "0.62rem", textTransform: "uppercase", letterSpacing: "0.1em", color: "rgba(255,255,255,0.26)", fontWeight: "600" },
  queueCount: { fontSize: "0.62rem", color: "rgba(255,255,255,0.18)", textTransform: "uppercase", letterSpacing: "0.08em", textAlign: "center" },
  // States
  centered: { position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "2rem", gap: "16px" },
  emptyIcon: { width: "68px", height: "68px", borderRadius: "50%", background: "rgba(96,165,250,0.09)", border: "1px solid rgba(96,165,250,0.18)", display: "flex", alignItems: "center", justifyContent: "center", color: "#60a5fa" },
  emptyTitle: { fontSize: "1.25rem", fontWeight: "700", margin: 0 },
  emptyDesc: { fontSize: "0.83rem", color: "rgba(255,255,255,0.38)", margin: 0, lineHeight: "1.5", maxWidth: "240px" },
  finalizeBtn: { display: "flex", alignItems: "center", gap: "8px", padding: "13px 26px", background: "rgba(16,185,129,0.2)", border: "1px solid rgba(16,185,129,0.38)", borderRadius: "14px", color: "#10b981", fontWeight: "700", fontSize: "0.88rem", cursor: "pointer" },
  spinner: { position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" },
  // Sync toast
  toast: {
    position: "fixed", bottom: "calc(env(safe-area-inset-bottom, 16px) + 72px)",
    left: "50%", transform: "translateX(-50%)",
    background: "rgba(248,113,113,0.15)", border: "1px solid rgba(248,113,113,0.3)",
    backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
    borderRadius: "100px", padding: "8px 18px",
    fontSize: "0.75rem", fontWeight: "600", color: "#f87171",
    whiteSpace: "nowrap", zIndex: 500,
  },
};

export default function CullPage() {
  const [photos, setPhotos] = useState([]);
  const [topIndex, setTopIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [reviewQueue, setReviewQueue] = useState(null);
  const [acceptedPaths, setAcceptedPaths] = useState([]);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState(null);
  // Track which photo IDs have a confirmed Firestore 200 OK write
  const [syncedPhotoIds, setSyncedPhotoIds] = useState(new Set());

  // ── Hooks ────────────────────────────────────────────────────────────
  const { status: syncStatus, latencyMs, isSyncing, markSyncing, markSyncComplete } = useSyncStatus();
  const { getObjectURL, preloadZoom, revokeCard } = useImageCache(photos, topIndex, syncStatus);

  // ── Firebase Subscriptions ───────────────────────────────────────────
  useEffect(() => {
    let unsubscribePhotos = null;

    const activeBatchRef = doc(db, "batches", "current_active");
    const unsubscribeBatch = onSnapshot(
      activeBatchRef,
      (snapshot) => {
        if (snapshot.exists()) {
          const batchData = snapshot.data();
          setReviewQueue(batchData);

          if (unsubscribePhotos) unsubscribePhotos();
          const photosQuery = query(
            collection(db, "photos"),
            where("batch_id", "==", batchData.batch_id),
            where("status", "==", "pending")
          );

          unsubscribePhotos = onSnapshot(
            photosQuery,
            (snap) => {
              const data = snap.docs
                .map((d) => ({ id: d.id, ...d.data() }))
                .sort((a, b) => (a.timestamp?.seconds || 0) - (b.timestamp?.seconds || 0));
              setPhotos(data);
              setTopIndex(0);
              setLoading(false);
              setError(null);
            },
            (err) => {
              console.error("Photos subscription error:", err);
              setError("Failed to stream photos from cloud.");
            }
          );
        } else {
          setLoading(false);
          setError("No active batch found. Run the Antigravity Engine first.");
        }
      },
      (err) => {
        console.error("Batch subscription error:", err);
        setError("Cloud Plane unreachable.");
        setLoading(false);
      }
    );

    return () => {
      unsubscribeBatch();
      if (unsubscribePhotos) unsubscribePhotos();
    };
  }, []);

  // ── Swipe Handler ────────────────────────────────────────────────────
  const handleSwipe = useCallback(
    async (photoId, batchId, status, swipeDurationMs, aiTier) => {
      markSyncing();

      // Optimistic: advance the top index first (instant UX)
      setPhotos((prev) => prev.filter((p) => p.id !== photoId));

      // Revoke object URLs for the evicted card to free memory
      revokeCard(photoId);

      if (status === "accepted") {
        const photo = photos.find((p) => p.id === photoId);
        if (photo?.original_path) setAcceptedPaths((prev) => [...prev, photo.original_path]);
      }

      try {
        const photoRef = doc(db, "photos", photoId);
        await updateDoc(photoRef, {
          status,
          user_id: auth.currentUser?.uid || "local_testing_user",
          decided_at: new Date().toISOString(),
          swipe_duration_ms: swipeDurationMs || null,
          // Full telemetry write-back (Step 3 of the audit)
          ai_tier_confirmed: aiTier || null,
          sync_confirmed_at: new Date().toISOString(),
        });

        // Mark this photo as synced (200 OK received)
        setSyncedPhotoIds((prev) => new Set([...prev, photoId]));

        const batchRef = doc(db, "batches", batchId);
        await updateDoc(batchRef, { processed_count: increment(1) });

        markSyncComplete();
      } catch (err) {
        console.error("Error updating decision:", err);
        markSyncComplete();
      }
    },
    [photos, revokeCard, markSyncing, markSyncComplete]
  );

  // ── Finalize ──────────────────────────────────────────────────────────
  const finalizeBatch = async () => {
    setIsFinalizing(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${baseUrl}/api/session/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accepted_file_paths: acceptedPaths }),
      });
      if (!res.ok) throw new Error("Stage 9 Handshake Failed");
      alert("🚀 Session closed. Master renders queued.");
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setIsFinalizing(false);
    }
  };

  // Deck: top 3 cards
  const deck = photos.slice(0, 3);

  return (
    <AuthGuard>
      <main style={S.main}>
        {/* ── Header ───────────────────────────────────────────────── */}
        <header style={S.header}>
          <div style={S.headerLeft}>
            <div style={S.headerIcon}>
              <Sparkles size={17} color="white" />
            </div>
            <span style={S.headerTitle}>HiLT Swipe</span>
            {photos.length > 0 && <span style={S.headerBadge}>{photos.length}</span>}
          </div>

          <div style={S.headerRight}>
            <Link href="/qa" style={S.headerBtn} title="History"><History size={15} /></Link>
            <Link href="/dashboard" style={S.headerBtn} title="Analytics"><BarChart2 size={15} /></Link>
            <button
              onClick={() => signOut(auth)}
              style={{ ...S.headerBtn, color: "#f87171", background: "rgba(248,113,113,0.07)" }}
              title="Sign out"
            >
              <LogOut size={15} />
            </button>
          </div>
        </header>

        {/* ── Swipe Area ───────────────────────────────────────────── */}
        <div style={S.swipeArea}>
          {loading && (
            <div style={S.spinner}>
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                style={{ width: "38px", height: "38px", border: "3px solid rgba(96,165,250,0.15)", borderTopColor: "#60a5fa", borderRadius: "50%" }}
              />
            </div>
          )}

          {!loading && error && (
            <div style={S.centered}>
              <div style={{ ...S.emptyIcon, background: "rgba(248,113,113,0.07)", border: "1px solid rgba(248,113,113,0.18)", color: "#f87171" }}>
                <AlertCircle size={30} />
              </div>
              <h2 style={S.emptyTitle}>Engine Offline</h2>
              <p style={S.emptyDesc}>{error}</p>
            </div>
          )}

          {!loading && !error && photos.length === 0 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} style={S.centered}>
              <div style={S.emptyIcon}><Sparkles size={30} /></div>
              <h2 style={S.emptyTitle}>Queue Clear!</h2>
              <p style={S.emptyDesc}>
                {reviewQueue?.total_photos ? `All ${reviewQueue.total_photos} photos processed.` : "All done!"}{" "}
                {acceptedPaths.length > 0 && `${acceptedPaths.length} kept.`}
              </p>
              {acceptedPaths.length > 0 && (
                <button style={S.finalizeBtn} onClick={finalizeBatch} disabled={isFinalizing}>
                  {isFinalizing ? "Processing…" : "🚀 Finalize & Render Masters"}
                </button>
              )}
            </motion.div>
          )}

          {/* Card Stack — render back-to-front so top card is on top */}
          <AnimatePresence>
            {deck
              .slice()
              .reverse()
              .map((photo, reversedIdx) => {
                const stackOffset = deck.length - 1 - reversedIdx; // 0=top
                const isTop = stackOffset === 0;
                return (
                  <SwipeCard
                    key={photo.id}
                    photo={photo}
                    isTop={isTop}
                    stackOffset={stackOffset}
                    cachedUrl={getObjectURL(photo.id)}
                    preloadZoom={preloadZoom}
                    syncStatus={syncStatus}
                    isSyncing={isSyncing}
                    latencyMs={latencyMs}
                    isSynced={syncedPhotoIds.has(photo.id)}
                    onSwipeStart={markSyncing}
                    onSwipe={(status, ms) =>
                      handleSwipe(photo.id, photo.batch_id, status, ms, photo.tier)
                    }
                  />
                );
              })}
          </AnimatePresence>
        </div>

        {/* ── Footer ───────────────────────────────────────────────── */}
        {!loading && !error && photos.length > 0 && (
          <footer style={S.footer}>
            <div style={S.footerHints}>
              <div style={S.hintGroup}>
                <div style={{ ...S.hintIcon, ...S.hintIconReject }}><ChevronLeft size={15} /></div>
                <span style={S.hintLabel}>Cull</span>
              </div>
              <span style={S.queueCount}>{photos.length} remaining</span>
              <div style={S.hintGroup}>
                <span style={S.hintLabel}>Keep</span>
                <div style={{ ...S.hintIcon, ...S.hintIconAccept }}><ChevronRight size={15} /></div>
              </div>
            </div>
          </footer>
        )}

        {/* ── Stalled / Offline Toast ──────────────────────────────── */}
        <AnimatePresence>
          {(syncStatus === "stalled" || syncStatus === "offline") && (
            <motion.div
              key="toast"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              style={S.toast}
            >
              {syncStatus === "offline"
                ? "⚠️ Local-First: Offline Mode — decisions cached"
                : "🔴 Reconnecting to Antigravity…"}
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </AuthGuard>
  );
}
