"use client";

import { motion, useMotionValue, useTransform } from "framer-motion";
import { useState } from "react";
import { Check, X, Info } from "lucide-react";
import styles from "../app/cull/cull.module.css";

export default function SwipeCard({ photo, onSwipe }) {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-25, 25]);
  const opacity = useTransform(x, [-200, -150, 0, 150, 200], [0, 1, 1, 1, 0]);
  
  const acceptOpacity = useTransform(x, [50, 150], [0, 1]);
  const rejectOpacity = useTransform(x, [-50, -150], [0, 1]);

  const handleDragEnd = (event, info) => {
    if (info.offset.x > 100) {
      onSwipe("accepted");
    } else if (info.offset.x < -100) {
      onSwipe("rejected");
    }
  };

  return (
    <motion.div
      style={{ x, rotate, opacity }}
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      onDragEnd={handleDragEnd}
      className={styles.cardWrapper}
    >
      <div className={styles.cardContent}>
        {/* Image */}
        <img 
          src={photo.rlhf_url || photo.url} 
          alt={photo.filename}
          className={styles.cardImage}
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
            <X size={64} className={styles.iconReject} />
          </div>
        </motion.div>

        {/* Metadata Footer */}
        <div className={styles.cardFooter}>
          <div className={styles.cardFooterInner}>
            <div>
              <p className={styles.cardMetaTier}>
                Tier {photo.tier} | Score: {photo.score ? photo.score.toFixed(2) : 'N/A'}
              </p>
              <h2 className={styles.cardTitle}>
                {photo.filename}
              </h2>
            </div>
            <button className={styles.cardInfoBtn}>
              <Info size={24} />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
