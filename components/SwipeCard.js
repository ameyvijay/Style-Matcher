"use client";

import { motion, useMotionValue, useTransform, AnimatePresence } from "framer-motion";
import { useState, useRef } from "react";
import { Check, X as XIcon, Info, XCircle } from "lucide-react";
import styles from "../app/cull/cull.module.css";

const TIER_MAP = {
  'Portfolio': '🏆 Tier: Portfolio',
  'Keeper': '✅ Tier: Keeper',
  'Review': '🔍 Tier: Review',
  'Cull': '❌ Tier: Bin',
  'Recoverable': '🔧 Tier: Recoverable'
};

export default function SwipeCard({ photo, onSwipe }) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const cardPresentedAt = useRef(Date.now());
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-25, 25]);
  const opacity = useTransform(x, [-200, -150, 0, 150, 200], [0, 1, 1, 1, 0]);
  
  const acceptOpacity = useTransform(x, [50, 150], [0, 1]);
  const rejectOpacity = useTransform(x, [-50, -150], [0, 1]);

  const handleDragEnd = (event, info) => {
    const swipeDurationMs = Date.now() - cardPresentedAt.current;
    if (info.offset.x > 100) {
      onSwipe("accepted", swipeDurationMs);
    } else if (info.offset.x < -100) {
      onSwipe("rejected", swipeDurationMs);
    }
  };

  const currentTier = TIER_MAP[photo.tier] || `Tier ${photo.tier}`;

  return (
    <>
      <motion.div
        style={{ x, rotate, opacity, touchAction: 'none' }}
        drag="x"
        dragConstraints={{ left: 0, right: 0 }}
        onDragEnd={handleDragEnd}
        className={styles.cardWrapper}
      >
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column' }} className={styles.cardContent}>
          {/* Main Image Section taking 75vh */}
          <div style={{ position: 'relative', height: '75vh', flexShrink: 0, width: '100%' }}>
            <img 
              src={photo.rlhf_url || photo.url} 
              alt={photo.filename}
              onClick={() => setIsFullscreen(true)}
              style={{ width: '100%', height: '100%', objectFit: 'cover', cursor: 'pointer' }}
            />

            {/* Overlays */}
            <motion.div 
              style={{ opacity: acceptOpacity }}
              className={`${styles.overlay} ${styles.overlayAccept}`}
            >
              <div className={styles.overlayIconWrapper}>
                <Check size={64} className={styles.iconAccept} />
              </div>
            </motion.div>

            <motion.div 
              style={{ opacity: rejectOpacity }}
              className={`${styles.overlay} ${styles.overlayReject}`}
            >
              <div className={styles.overlayIconWrapper}>
                <XIcon size={64} className={styles.iconReject} />
              </div>
            </motion.div>
          </div>

          {/* Below the Fold Metadata */}
          <div style={{ padding: '1.5rem', backgroundColor: '#111827', color: 'white' }}>
            <h2 className={styles.cardTitle}>{photo.filename}</h2>
            <p className={styles.cardMetaTier} style={{ marginTop: '0.5rem', marginBottom: '1rem' }}>
              {currentTier} | Score: {photo.score ? photo.score.toFixed(2) : 'N/A'}
            </p>
            
            <div style={{ marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 'bold', marginBottom: '0.5rem', color: '#9ca3af' }}>AI Coach Summary</h3>
              <p style={{ fontSize: '0.875rem', lineHeight: '1.4' }}>{photo.ai_summary || "No summary available."}</p>
            </div>

            <div style={{ backgroundColor: '#1f2937', padding: '1rem', borderRadius: '0.5rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 'bold', marginBottom: '0.5rem', color: '#9ca3af' }}>EXIF Data</h3>
              <ul style={{ listStyleType: 'none', padding: 0, margin: 0, fontSize: '0.875rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <li><strong>Focal Length:</strong> {photo.focal_length || "N/A"}</li>
                <li><strong>Aperture:</strong> {photo.aperture || "N/A"}</li>
                <li><strong>Shutter:</strong> {photo.shutter_speed || "N/A"}</li>
                <li><strong>ISO:</strong> {photo.iso || "N/A"}</li>
              </ul>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Tap-to-Fullscreen Modal */}
      <AnimatePresence>
        {isFullscreen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed',
              top: 0, left: 0, right: 0, bottom: 0,
              backgroundColor: 'rgba(0,0,0,0.95)',
              zIndex: 100,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              touchAction: 'none'
            }}
            onClick={() => setIsFullscreen(false)}
          >
            <button 
              onClick={() => setIsFullscreen(false)}
              style={{
                position: 'absolute', top: '1rem', right: '1rem',
                background: 'transparent', border: 'none', color: 'white', cursor: 'pointer',
                zIndex: 101, padding: '0.5rem'
              }}
            >
              <XCircle size={32} />
            </button>
            <img 
              src={photo.rlhf_url || photo.url} 
              alt={photo.filename}
              style={{ maxWidth: '100vw', maxHeight: '100vh', objectFit: 'contain' }}
              onClick={(e) => e.stopPropagation()}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
