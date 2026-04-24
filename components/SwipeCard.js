"use client";

import {
  motion,
  useMotionValue,
  useTransform,
  AnimatePresence,
  useSpring,
} from "framer-motion";
import { useState, useRef, useCallback, useEffect } from "react";
import {
  Check,
  X as XIcon,
  ZoomIn,
  ChevronUp,
  ChevronDown,
  X as CloseIcon,
  Camera,
  Aperture,
  Clock,
  Zap,
  Star,
  AlertTriangle,
  Shield,
  Wifi,
  WifiOff,
  Activity,
  Sun,
  ScanLine,
  CalendarDays,
  Tag,
  Maximize2,
  SlidersHorizontal,
} from "lucide-react";

// Keyed by BOTH Title Case and lowercase to match backend outputs without transformation.
// Backend (Python) emits: "portfolio"/"keeper"/"review"/"cull"
// TIER_CONFIG lookup normalises via: TIER_CONFIG[tier] || TIER_CONFIG[capitalise(tier)]
const TIER_CONFIG = {
  // Title Case keys (legacy + manual use)
  Portfolio:   { label: "Portfolio",   icon: "🏆", color: "#f59e0b", bg: "rgba(245,158,11,0.15)",  border: "rgba(245,158,11,0.4)"  },
  Keeper:      { label: "Keeper",      icon: "✅", color: "#10b981", bg: "rgba(16,185,129,0.15)",  border: "rgba(16,185,129,0.4)"  },
  Review:      { label: "Review",      icon: "🔍", color: "#60a5fa", bg: "rgba(96,165,250,0.15)",  border: "rgba(96,165,250,0.4)"  },
  Cull:        { label: "Cull",        icon: "❌", color: "#f87171", bg: "rgba(248,113,113,0.15)", border: "rgba(248,113,113,0.4)" },
  Recoverable: { label: "Salvageable", icon: "🔧", color: "#a78bfa", bg: "rgba(167,139,250,0.15)", border: "rgba(167,139,250,0.4)" },
  // Lowercase aliases — exact match for backend Firestore payloads
  portfolio:   { label: "Portfolio",   icon: "🏆", color: "#f59e0b", bg: "rgba(245,158,11,0.15)",  border: "rgba(245,158,11,0.4)"  },
  keeper:      { label: "Keeper",      icon: "✅", color: "#10b981", bg: "rgba(16,185,129,0.15)",  border: "rgba(16,185,129,0.4)"  },
  review:      { label: "Review",      icon: "🔍", color: "#60a5fa", bg: "rgba(96,165,250,0.15)",  border: "rgba(96,165,250,0.4)"  },
  cull:        { label: "Cull",        icon: "❌", color: "#f87171", bg: "rgba(248,113,113,0.15)", border: "rgba(248,113,113,0.4)" },
};

/** Safe tier lookup: handles lowercase, Title Case, and undefined. */
function getTier(rawTier) {
  if (!rawTier) return TIER_CONFIG["review"];
  return TIER_CONFIG[rawTier] || TIER_CONFIG[rawTier.toLowerCase()] || TIER_CONFIG["review"];
}

const SWIPE_THRESHOLD = 110;
const ZOOM_PRELOAD_DELAY_MS = 200; // Don't preload full-res until 200ms hold

/**
 * SKIP_THRESHOLD — vertical drag distance (px) required to trigger a "Skip / Review Later"
 * gesture. Deliberately higher than the horizontal SWIPE_THRESHOLD so the user has to be
 * intentional about it.
 *
 * TODO (Skip / Review Later):
 *   - On upward skip: call onSwipe("skipped", ms) and POST /api/annotations/skip { photo_hash }
 *   - Backend should move the photo to the end of the Firestore queue (re-enqueue) rather
 *     than writing an Annotation row, preserving "undecided" status.
 *   - Add a dedicated SkipQueue view in the Data Governance tab to surface skipped items.
 */
const SKIP_THRESHOLD = 140;

// ── Sync Pulse Indicator ───────────────────────────────────────────────
const SYNC_PULSE_CONFIG = {
  optimal:   { color: "#10b981", label: "Optimal",      Icon: Activity },
  throttled: { color: "#f59e0b", label: "Catching Up",  Icon: Wifi     },
  stalled:   { color: "#f87171", label: "Stalled",      Icon: AlertTriangle },
  offline:   { color: "#f87171", label: "Offline",      Icon: WifiOff  },
  syncing:   { color: "#60a5fa", label: "Syncing…",     Icon: Activity },
};

function SyncPulse({ syncStatus, isSyncing, latencyMs }) {
  const state = isSyncing ? "syncing" : syncStatus;
  const cfg = SYNC_PULSE_CONFIG[state] || SYNC_PULSE_CONFIG.optimal;
  const { Icon } = cfg;

  return (
    <div style={{ ...styles.syncPulseWrapper }} title={`${cfg.label}${latencyMs ? ` · ${latencyMs}ms` : ""}`}>
      {/* Animated ring for non-optimal states */}
      {state !== "optimal" && (
        <motion.div
          animate={{ scale: [1, 1.6, 1], opacity: [0.6, 0, 0.6] }}
          transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
          style={{ ...styles.syncRing, borderColor: cfg.color }}
        />
      )}
      <div style={{ ...styles.syncDot, background: cfg.color }}>
        <Icon size={9} color="#000" strokeWidth={2.5} />
      </div>
    </div>
  );
}

// ── Progressive Image Loader ───────────────────────────────────────────
// Shows blurhash/tiny thumbnail instantly, swaps in full cache URL when ready.
function ProgressiveImage({ src, placeholderDataUrl, alt, style, onLoad }) {
  const [loaded, setLoaded] = useState(false);
  const imgRef = useRef(null);

  // If src changes, reset loaded state
  useEffect(() => {
    setLoaded(false);
  }, [src]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      {/* Placeholder — tiny base64 thumbnail or gradient */}
      {placeholderDataUrl && !loaded && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: `url(${placeholderDataUrl})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            filter: "blur(12px)",
            transform: "scale(1.05)",
            transition: "opacity 0.3s",
          }}
        />
      )}
      {!loaded && !placeholderDataUrl && (
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(135deg, #111 0%, #1a1a2e 100%)" }} />
      )}
      {/* Real image — fade in on load */}
      <img
        ref={imgRef}
        src={src}
        alt={alt}
        style={{
          ...style,
          opacity: loaded ? 1 : 0,
          transition: "opacity 0.35s ease",
        }}
        draggable="false"
        onLoad={() => {
          setLoaded(true);
          onLoad?.();
        }}
      />
    </div>
  );
}

// ── Main SwipeCard Component ───────────────────────────────────────────
export default function SwipeCard({
  photo,
  onSwipe,
  isTop,
  stackOffset = 0,   // 0=top, 1=second, 2=third
  // Image cache interface (from useImageCache)
  cachedUrl,         // best cached URL for this card
  preloadZoom,       // fn() → preloads full-res
  // Sync health (from useSyncStatus in parent)
  syncStatus = "optimal",
  isSyncing = false,
  latencyMs = null,
  isSynced = false,    // true once Firestore write returns 200 OK
  onSwipeStart,      // parent notifies sync hook to mark syncing
}) {
  const [screen, setScreen] = useState("hero");
  const cardPresentedAt = useRef(null);

  useEffect(() => {
    cardPresentedAt.current = Date.now();
  }, []);

  const stopProp = useCallback((e) => e.stopPropagation(), []);

  // Physics-based drag — horizontal axis (keep / cull)
  const x = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 420, damping: 42 });
  const rotate = useTransform(x, [-260, 260], [-20, 20]);
  const cardOpacity = useTransform(x, [-260, -190, 0, 190, 260], [0, 1, 1, 1, 0]);
  const acceptOpacity = useTransform(x, [30, SWIPE_THRESHOLD], [0, 1]);
  const rejectOpacity = useTransform(x, [-30, -SWIPE_THRESHOLD], [0, 1]);
  
  // New: Shrink the card slightly when dragging to make it feel more manageable
  const scale = useTransform(x, [-SWIPE_THRESHOLD, 0, SWIPE_THRESHOLD], [0.88, 1, 0.88]);

  /**
   * TODO (Skip / Review Later — vertical axis):
   * y is intentionally wired but the skip action is NOT yet implemented.
   * When the user drags upward past SKIP_THRESHOLD, show the SKIP overlay
   * and call onSwipe("skipped", ms).  Downward drag is reserved for a future
   * "Super Cull" (immediate delete) gesture — leave dragConstraints.bottom: 0
   * until that feature is specced.
   */
  const y = useMotionValue(0);
  // skipOpacity fades in as the card moves upward (negative y)
  const skipOpacity = useTransform(y, [-30, -SKIP_THRESHOLD], [0, 1]);

  const tier = getTier(photo.tier);
  const imageUrl = cachedUrl || photo.rlhf_url || photo.url;
  const placeholder = photo.thumbnail_data_url || photo.blurhash_url || null;

  // ── Drag handlers ──────────────────────────────────────────────────
  const handleDragEnd = useCallback(
    (_, info) => {
      const ms = Date.now() - cardPresentedAt.current;

      // Horizontal: keep / cull (existing logic)
      if (info.offset.x > SWIPE_THRESHOLD) {
        onSwipeStart?.();
        onSwipe("accepted", ms);
      } else if (info.offset.x < -SWIPE_THRESHOLD) {
        onSwipeStart?.();
        onSwipe("rejected", ms);

      // Vertical: skip / review later
      } else if (info.offset.y < -SKIP_THRESHOLD) {
        onSwipeStart?.();
        onSwipe("skipped", ms);
      }
    },
    [onSwipe, onSwipeStart]
  );

  // ── Zoom open ────────────────────────────────────────────────────────
  const openZoom = useCallback(
    (e) => {
      stopProp(e);
      setScreen("zoom");
      // Background preload for future full-res — non-blocking
      preloadZoom?.(photo);
    },
    [stopProp, preloadZoom, photo]
  );

  // ── Spec sheet data ────────────────────────────────────────────
  const exif = photo.exif || {};
  const coaching = photo.coaching || {};

  // ── Diagnostic Guard (remove in production) ───────────────────
  // Fires once per top-card mount. Alerts on empty metric keys so
  // schema mismatches (e.g. snake_case vs camelCase) surface instantly.
  useEffect(() => {
    if (!isTop) return;
    const metricAudit = {
      composite_score: photo.composite_score ?? photo.score,
      sharpness_score: photo.sharpness_score,
      aesthetic_score: photo.aesthetic_score,
      exposure_score: photo.exposure_score,
      tier: photo.tier,
      genre: photo.genre,
      exif_keys: Object.keys(exif),
      reasoning: photo.reasoning,
    };
    console.log("[SwipeCard] 📊 Photo payload audit:", metricAudit);
    const undefinedKeys = Object.entries(metricAudit)
      .filter(([, v]) => v === undefined || v === null)
      .map(([k]) => k);
    if (undefinedKeys.length > 0) {
      console.warn("[SwipeCard] ⚠️ Undefined metric keys — check Firestore schema:", undefinedKeys);
    }
  }, [photo.id, isTop]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Core 4-field bento grid (2×2) ──
  const exifGrid = [
    { icon: <Zap size={14} />,      label: "ISO",     value: String(exif.ISO     || photo.iso           || "—") },
    { icon: <Aperture size={14} />, label: "Aperture", value: String(exif.Aperture|| photo.aperture       || "—") },
    { icon: <Clock size={14} />,    label: "Shutter",  value: String(exif.Shutter || photo.shutter_speed  || "—") },
    { icon: <Camera size={14} />,   label: "Focal",    value: String(exif.FocalLength || photo.focal_length || "—") },
  ];

  // ── Extended EXIF rows (all remaining fields) ──
  const exifExtended = [
    exif.Make || exif.Model ? {
      icon: <Camera size={13} />,
      label: "Camera",
      value: [exif.Make, exif.Model].filter(Boolean).join(" ") || "—",
    } : null,
    exif.LensModel ? {
      icon: <ScanLine size={13} />,
      label: "Lens",
      value: exif.LensModel,
    } : null,
    exif.WhiteBalance !== undefined ? {
      icon: <Sun size={13} />,
      label: "White Balance",
      value: String(exif.WhiteBalance ?? "—"),
    } : null,
    exif.MeteringMode !== undefined ? {
      icon: <SlidersHorizontal size={13} />,
      label: "Metering",
      value: String(exif.MeteringMode ?? "—"),
    } : null,
    exif.ExposureCompensation !== undefined ? {
      icon: <SlidersHorizontal size={13} />,
      label: "Exposure Comp",
      value: exif.ExposureCompensation != null
        ? (Number(exif.ExposureCompensation) >= 0 ? `+${exif.ExposureCompensation}` : String(exif.ExposureCompensation)) + " EV"
        : "—",
    } : null,
    (exif.ImageWidth && exif.ImageHeight) ? {
      icon: <Maximize2 size={13} />,
      label: "Dimensions",
      value: `${exif.ImageWidth} × ${exif.ImageHeight}`,
    } : null,
    exif.DateTime ? {
      icon: <CalendarDays size={13} />,
      label: "Captured",
      value: exif.DateTime,
    } : null,
  ].filter(Boolean);

  const scores = [
    { label: "Sharpness", value: photo.sharpness_score ?? photo.sharpness ?? photo.sharp ?? null, color: "#60a5fa" },
    { label: "Aesthetic",  value: photo.aesthetic_score  ?? photo.aesthetic ?? photo.aes ?? null, color: "#a78bfa" },
    { label: "Exposure",   value: photo.exposure_score   ?? photo.exposure ?? null, color: "#10b981" },
    { label: "Composite",  value: photo.composite_score  ?? photo.score ?? null, color: "#f59e0b" },
  ];

  const ScoreBar = ({ label, value, color }) => {
    const pct = value != null ? Math.round(value) : null;
    return (
      <div style={styles.scoreRow}>
        <span style={styles.scoreLabel}>{label}</span>
        <div style={styles.scoreTrack}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: pct != null ? `${pct}%` : "0%" }}
            transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1], delay: 0.1 }}
            style={{ ...styles.scoreBar, background: `linear-gradient(90deg, ${color}88, ${color})` }}
          />
        </div>
        <span style={{ ...styles.scoreValue, color }}>{pct ?? "—"}</span>
      </div>
    );
  };

  const aiSummary   = photo.reasoning || photo.ai_summary || "No AI coaching data available for this image.";
  const coachPriority = coaching.improvement_priority || "";
  const coachComp     = coaching.composition || "";
  const stackScale = isTop ? 1 : 1 - stackOffset * 0.04;
  const stackY     = isTop ? 0 : stackOffset * 10;

  return (
    <>
      {/* ── SCREEN 1: HERO CARD ─────────────────────────────────────── */}
      <motion.div
        style={{
          x: isTop ? x : 0,
          y: isTop ? y : stackY,
          rotate: isTop ? rotate : 0,
          opacity: isTop ? cardOpacity : 1,
          scale: isTop ? scale : stackScale,
          touchAction: "none",
          ...styles.cardWrapper,
          zIndex: 10 - stackOffset,
        }}
        drag={isTop ? true : false}
        dragConstraints={{
          left: 0,
          right: 0,
          top: -SKIP_THRESHOLD * 1.5,
          bottom: 0,
        }}
        dragElastic={0.15}
        onDragEnd={handleDragEnd}
      >
        <div style={styles.card}>
          <div style={{ position: "relative", width: "100%", height: "100%" }}>
            {/* Progressive image */}
            <ProgressiveImage
              src={imageUrl}
              placeholderDataUrl={placeholder}
              alt={photo.filename}
              style={styles.image}
            />

            {/* KEEP overlay */}
            <motion.div style={{ ...styles.overlay, ...styles.overlayAccept, opacity: acceptOpacity }}>
              <div style={styles.overlayBadge}>
                <Check size={38} strokeWidth={3} color="#10b981" />
                <span style={{ ...styles.overlayLabel, color: "#10b981" }}>KEEP</span>
              </div>
            </motion.div>

            {/* CULL overlay */}
            <motion.div style={{ ...styles.overlay, ...styles.overlayReject, opacity: rejectOpacity }}>
              <div style={styles.overlayBadge}>
                <XIcon size={38} strokeWidth={3} color="#f87171" />
                <span style={{ ...styles.overlayLabel, color: "#f87171" }}>CULL</span>
              </div>
            </motion.div>

            {/**
             * SKIP overlay — appears on upward vertical drag.
             * TODO: activate once skip endpoint is wired; currently opacity stays 0
             * because y MotionValue is not yet bound to the card's y style prop.
             * To enable: change card's `y` style to `y: isTop ? y : stackY`.
             */}
            {isTop && (
              <motion.div style={{ ...styles.overlay, ...styles.overlaySkip, opacity: skipOpacity }}>
                <div style={styles.overlayBadge}>
                  <ChevronUp size={38} strokeWidth={3} color="#60a5fa" />
                  <span style={{ ...styles.overlayLabel, color: "#60a5fa" }}>SKIP</span>
                </div>
              </motion.div>
            )}

            {/* Top HUD: tier, score, sync pulse */}
            <div style={styles.topHud}>
              <div style={{ ...styles.tierBadge, background: tier.bg, border: `1px solid ${tier.border}`, color: tier.color }}>
                <span>{tier.icon}</span>
                <span style={styles.tierText}>{tier.label}</span>
              </div>
              <div style={styles.topHudRight}>
                {photo.composite_score != null && (
                  <div style={styles.scoreBadge}>
                    <Star size={11} color="#f59e0b" fill="#f59e0b" />
                    <span style={styles.scoreText}>{Math.round(photo.composite_score ?? photo.score ?? 0)}</span>
                  </div>
                )}
                {isTop && (
                  <SyncPulse syncStatus={syncStatus} isSyncing={isSyncing} latencyMs={latencyMs} />
                )}
              </div>
            </div>

            {/* Right-edge action rail — clear of HUD and footer text */}
            {isTop && (
              <div style={styles.sideRail}>
                <button
                  style={styles.railBtn}
                  onPointerDown={stopProp}
                  onClick={openZoom}
                  aria-label="Pixel-peep zoom"
                >
                  <ZoomIn size={17} />
                </button>
                <div style={styles.railDivider} />
                <button
                  style={{ ...styles.railBtn, ...styles.railBtnPrimary }}
                  onPointerDown={stopProp}
                  onClick={(e) => { stopProp(e); setScreen("spec"); }}
                  aria-label="View metadata"
                >
                  <ChevronUp size={17} />
                </button>
              </div>
            )}

            {/* Bottom footer — text only, full width */}
            <div style={styles.cardFooter}>
              <span style={styles.cardFilename} title={photo.filename}>{photo.filename}</span>
              <span style={styles.cardGenre}>{photo.genre || exif.Make || ""}</span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* ── SCREEN 2: SPEC SHEET (slide up) ────────────────────────── */}
      <AnimatePresence>
        {screen === "spec" && (
          <motion.div
            key="spec"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 34, stiffness: 340 }}
            style={styles.specSheet}
          >
            <div style={styles.specHandle} />
            <button style={styles.specCloseBtn} onClick={() => setScreen("hero")} aria-label="Close">
              <ChevronDown size={22} />
            </button>

            <div style={styles.specScroll}>
              {/* Header: filename + camera + sync status */}
              <div style={styles.specHeader}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                  <h2 style={{ ...styles.specFilename, marginBottom: 0 }}>{photo.filename}</h2>
                  {/* ── Data Synced indicator ── */}
                  {isSynced ? (
                    <div style={styles.syncedBadge}>
                      <Check size={10} strokeWidth={3} /><span>Synced</span>
                    </div>
                  ) : (
                    <div style={{ ...styles.syncedBadge, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.28)" }}>
                      <Activity size={10} /><span>Pending</span>
                    </div>
                  )}
                </div>
                {(exif.Make || exif.Model) && (
                  <p style={styles.specCamera}>{exif.Make} {exif.Model}</p>
                )}
              </div>

              {/* AI Classification Banner */}
              <div style={styles.classificationBanner}>
                <div style={styles.classificationLeft}>
                  <div style={{ ...styles.specTierBadge, background: tier.bg, border: `1px solid ${tier.border}`, color: tier.color, marginBottom: 0 }}>
                    {tier.icon} {tier.label}
                  </div>
                  <span style={styles.classificationSubLabel}>AI Tier</span>
                </div>
                <div style={styles.classificationDivider} />
                <div style={styles.classificationRight}>
                  <span style={styles.classificationScore}>
                    {photo.composite_score != null
                      ? Math.round(photo.composite_score ?? photo.score ?? 0)
                      : "—"}
                  </span>
                  <span style={styles.classificationSubLabel}>/ 100</span>
                </div>
                <div style={styles.classificationDivider} />
                <div style={styles.classificationRight}>
                  <span style={{ ...styles.classificationScore, color: "#60a5fa", fontSize: "0.85rem" }}>
                    {photo.genre || exif ? (photo.genre || "General") : "—"}
                  </span>
                  <span style={styles.classificationSubLabel}>Genre</span>
                </div>
              </div>

              {/* Core Bento EXIF Grid (2×2) */}
              <div style={styles.bentoGrid}>
                {exifGrid.map((item, i) => (
                  <div key={i} style={styles.bentoCell}>
                    <div style={styles.bentoCellIcon}>{item.icon}</div>
                    <span style={styles.bentoCellLabel}>{item.label}</span>
                    <span style={styles.bentoCellValue}>{item.value}</span>
                  </div>
                ))}
              </div>

              {/* Extended EXIF metadata rows */}
              {exifExtended.length > 0 && (
                <div style={styles.exifExtendedList}>
                  {exifExtended.map((item, i) => (
                    <div key={i} style={styles.exifExtendedRow}>
                      <div style={styles.exifExtendedIcon}>{item.icon}</div>
                      <span style={styles.exifExtendedLabel}>{item.label}</span>
                      <span style={styles.exifExtendedValue}>{item.value}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Quality Scores */}
              <div style={styles.section}>
                <h3 style={styles.sectionTitle}>Quality Analysis</h3>
                <div style={styles.scoreList}>
                  {scores.map((s) => <ScoreBar key={s.label} {...s} />)}
                </div>
              </div>

              {/* AI Coach Card */}
              <div style={styles.coachCard}>
                <div style={styles.coachHeader}>
                  <Shield size={15} color="#60a5fa" />
                  <span style={styles.coachTitle}>AI Coach Assessment</span>
                  <span style={styles.coachVersion}>{photo.prompt_version || "v1.0"}</span>
                </div>
                <p style={styles.coachReasoning}>{aiSummary}</p>
                {coachPriority && (
                  <div style={styles.priorityBox}>
                    <AlertTriangle size={13} color="#f59e0b" />
                    <p style={styles.priorityText}>{coachPriority}</p>
                  </div>
                )}
                {coachComp && <p style={styles.coachComposition}>{coachComp}</p>}
              </div>

              {/* RAG Context */}
              {photo.semantic_description && (
                <div style={styles.ragCard}>
                  <div style={styles.ragHeader}>
                    <Zap size={13} color="#a78bfa" />
                    <span style={styles.ragTitle}>RAG Context</span>
                  </div>
                  <p style={styles.ragText}>{photo.semantic_description}</p>
                </div>
              )}

              {/* Action Buttons */}
              <div style={styles.specActions}>
                <button
                  style={{ ...styles.swipeBtn, ...styles.swipeBtnReject }}
                  onPointerDown={stopProp}
                  onClick={(e) => {
                    stopProp(e);
                    setScreen("hero");
                    onSwipeStart?.();
                    setTimeout(() => onSwipe("rejected", Date.now() - cardPresentedAt.current), 50);
                  }}
                >
                  <XIcon size={19} /><span>Cull</span>
                </button>
                <button
                  style={{ ...styles.swipeBtn, ...styles.swipeBtnAccept }}
                  onPointerDown={stopProp}
                  onClick={(e) => {
                    stopProp(e);
                    setScreen("hero");
                    onSwipeStart?.();
                    setTimeout(() => onSwipe("accepted", Date.now() - cardPresentedAt.current), 50);
                  }}
                >
                  <Check size={19} /><span>Keep</span>
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── SCREEN 3: PIXEL-PEEP ZOOM ───────────────────────────────── */}
      <AnimatePresence>
        {screen === "zoom" && (
          <motion.div
            key="zoom"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            style={styles.zoomModal}
          >
            <button style={styles.zoomCloseBtn} onClick={() => setScreen("hero")}>
              <CloseIcon size={22} />
            </button>

            {/* HUD */}
            <div style={styles.zoomHud}>
              <div style={{ ...styles.tierBadge, background: tier.bg, border: `1px solid ${tier.border}`, color: tier.color }}>
                {tier.icon} {tier.label}
              </div>
              {photo.composite_score != null && (
                <span style={{ color: "#f59e0b", fontSize: "0.75rem", fontWeight: "700", display: "flex", alignItems: "center", gap: "4px" }}>
                  <Star size={11} color="#f59e0b" fill="#f59e0b" />
                  {Math.round(photo.composite_score ?? 0)}/100
                </span>
              )}
            </div>

            {/* Full image — show best available URL, sharp, no blur */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100vw", height: "100vh" }}>
              <motion.img
                key={imageUrl}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.22 }}
                src={imageUrl}
                alt={photo.filename}
                style={{
                    ...styles.zoomImage,
                    touchAction: "none"
                }}
                drag
                dragConstraints={{ left: -500, right: 500, top: -500, bottom: 500 }}
                dragElastic={0.1}
                draggable="false"
              />
            </div>

            {/* EXIF footer */}
            <div style={styles.zoomFooter}>
              <span style={styles.zoomFilename}>{photo.filename}</span>
              {exif.ISO && (
                <span style={styles.zoomExif}>
                  ISO {exif.ISO} · {exif.Aperture} · {exif.Shutter} · {exif.FocalLength}
                </span>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ── Styles ────────────────────────────────────────────────────────────
const GLASS = {
  background: "rgba(8,8,12,0.92)",
  backdropFilter: "blur(28px)",
  WebkitBackdropFilter: "blur(28px)",
};

const styles = {
  cardWrapper: {
    position: "absolute",
    inset: 0,
    userSelect: "none",
    willChange: "transform",
    transformOrigin: "bottom center",
  },
  card: {
    position: "relative",
    width: "100%",
    height: "100%",
    borderRadius: "28px",
    overflow: "hidden",
    boxShadow: "0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.06)",
  },
  image: { width: "100%", height: "100%", objectFit: "cover", display: "block", pointerEvents: "none" },
  overlay: { position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", pointerEvents: "none" },
  overlayAccept: { background: "rgba(16,185,129,0.32)" },
  overlayReject: { background: "rgba(248,113,113,0.32)" },
  /** TODO: overlaySkip is ready for the vertical Skip gesture. Background intentionally blue-tinted. */
  overlaySkip:   { background: "rgba(96,165,250,0.32)" },
  overlayBadge: { display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", background: "rgba(0,0,0,0.55)", borderRadius: "20px", padding: "18px 28px", backdropFilter: "blur(12px)", border: "1.5px solid rgba(255,255,255,0.12)" },
  overlayLabel: { fontSize: "1rem", fontWeight: "800", letterSpacing: "0.22em" },
  // HUD
  topHud: { position: "absolute", top: "15px", left: "15px", right: "15px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", pointerEvents: "none" },
  topHudRight: { display: "flex", alignItems: "center", gap: "6px" },
  tierBadge: { display: "inline-flex", alignItems: "center", gap: "5px", padding: "5px 11px", borderRadius: "100px", fontSize: "0.7rem", fontWeight: "700", letterSpacing: "0.04em", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)" },
  tierText: { textTransform: "uppercase" },
  scoreBadge: { display: "inline-flex", alignItems: "center", gap: "4px", padding: "5px 9px", borderRadius: "100px", background: "rgba(245,158,11,0.15)", border: "1px solid rgba(245,158,11,0.4)", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)" },
  scoreText: { color: "#f59e0b", fontSize: "0.78rem", fontWeight: "700" },
  // Sync Pulse
  syncPulseWrapper: { position: "relative", width: "22px", height: "22px", display: "flex", alignItems: "center", justifyContent: "center" },
  syncRing: { position: "absolute", inset: "-3px", borderRadius: "50%", border: "1.5px solid", opacity: 0 },
  syncDot: { width: "20px", height: "20px", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" },
  // Footer
  cardFooter: {
    position: "absolute", bottom: 0, left: 0, right: 0,
    padding: "60px 18px 20px",
    paddingRight: "72px",
    background: "linear-gradient(to top, rgba(0,0,0,0.94) 0%, rgba(0,0,0,0.5) 60%, transparent 100%)",
    display: "flex", flexDirection: "column", gap: "3px",
    pointerEvents: "none",    // decorative only — never intercept taps
  },
  cardFilename: { fontSize: "0.95rem", fontWeight: "700", color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", letterSpacing: "-0.01em" },
  cardGenre: { fontSize: "0.65rem", color: "rgba(255,255,255,0.38)", textTransform: "uppercase", letterSpacing: "0.08em" },
  // Right-edge vertical action rail
  sideRail: {
    position: "absolute",
    right: "14px",
    bottom: "64px",
    zIndex: 10,                 // above cardFooter gradient
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "0",
    background: "rgba(0,0,0,0.45)",
    backdropFilter: "blur(16px)",
    WebkitBackdropFilter: "blur(16px)",
    border: "1px solid rgba(255,255,255,0.12)",
    borderRadius: "22px",
    overflow: "hidden",
  },
  railBtn: {
    width: "44px", height: "44px",
    display: "flex", alignItems: "center", justifyContent: "center",
    background: "transparent",
    border: "none",
    color: "rgba(255,255,255,0.75)",
    cursor: "pointer",
    flexShrink: 0,
  },
  railBtnPrimary: {
    color: "#60a5fa",
    background: "rgba(96,165,250,0.12)",
  },
  railDivider: {
    width: "28px", height: "1px",
    background: "rgba(255,255,255,0.1)",
    flexShrink: 0,
  },
  // Spec Sheet
  specSheet: { position: "fixed", inset: 0, zIndex: 200, ...GLASS, display: "flex", flexDirection: "column", paddingTop: "env(safe-area-inset-top, 16px)", paddingBottom: "env(safe-area-inset-bottom, 0)" },
  specHandle: { width: "40px", height: "4px", borderRadius: "4px", background: "rgba(255,255,255,0.18)", margin: "12px auto 0", flexShrink: 0 },
  specCloseBtn: { position: "absolute", top: "calc(env(safe-area-inset-top, 16px) + 8px)", right: "16px", width: "36px", height: "36px", borderRadius: "50%", background: "rgba(255,255,255,0.09)", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" },
  specScroll: { flex: 1, overflowY: "auto", padding: "14px 18px 24px", WebkitOverflowScrolling: "touch" },
  specHeader: { marginBottom: "14px", paddingTop: "8px" },
  specTierBadge: { display: "inline-flex", alignItems: "center", gap: "6px", padding: "5px 12px", borderRadius: "100px", fontSize: "0.7rem", fontWeight: "700", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "10px" },
  specFilename: { fontSize: "1.25rem", fontWeight: "700", color: "#fff", margin: "0 0 4px", letterSpacing: "-0.02em" },
  specCamera: { fontSize: "0.72rem", color: "rgba(255,255,255,0.38)", fontFamily: "'Courier New', monospace", margin: 0 },
  syncedBadge: {
    display: "inline-flex", alignItems: "center", gap: "4px",
    padding: "3px 9px", borderRadius: "100px", fontSize: "0.6rem", fontWeight: "700",
    letterSpacing: "0.06em", textTransform: "uppercase", flexShrink: 0,
    background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.3)", color: "#10b981",
  },
  // Classification Banner
  classificationBanner: { display: "flex", alignItems: "center", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "16px", padding: "14px 16px", marginBottom: "18px", gap: "0" },
  classificationLeft: { display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "4px", flex: 1 },
  classificationRight: { display: "flex", flexDirection: "column", alignItems: "center", gap: "4px", flex: 1 },
  classificationDivider: { width: "1px", alignSelf: "stretch", background: "rgba(255,255,255,0.1)", margin: "0 12px" },
  classificationScore: { fontSize: "1.6rem", fontWeight: "800", color: "#f59e0b", letterSpacing: "-0.04em", lineHeight: 1, fontFamily: "'Courier New', monospace" },
  classificationSubLabel: { fontSize: "0.6rem", textTransform: "uppercase", letterSpacing: "0.1em", color: "rgba(255,255,255,0.3)", fontWeight: "600" },
  // Extended EXIF list
  exifExtendedList: { background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: "12px", overflow: "hidden", marginBottom: "20px" },
  exifExtendedRow: { display: "flex", alignItems: "center", gap: "10px", padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.05)" },
  exifExtendedIcon: { color: "rgba(255,255,255,0.28)", flexShrink: 0, width: "16px", display: "flex", alignItems: "center" },
  exifExtendedLabel: { fontSize: "0.68rem", color: "rgba(255,255,255,0.38)", textTransform: "uppercase", letterSpacing: "0.08em", width: "100px", flexShrink: 0 },
  exifExtendedValue: { fontSize: "0.8rem", color: "rgba(255,255,255,0.82)", fontFamily: "'Courier New', monospace", flex: 1, textAlign: "right" },
  // Bento Grid
  bentoGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1px", background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "16px", overflow: "hidden", marginBottom: "22px" },
  bentoCell: { background: "rgba(255,255,255,0.025)", padding: "15px", display: "flex", flexDirection: "column", gap: "4px" },
  bentoCellIcon: { color: "rgba(255,255,255,0.3)", marginBottom: "2px" },
  bentoCellLabel: { fontSize: "0.62rem", textTransform: "uppercase", letterSpacing: "0.12em", color: "rgba(255,255,255,0.32)" },
  bentoCellValue: { fontSize: "1.05rem", fontWeight: "700", color: "#fff", fontFamily: "'Courier New', monospace", letterSpacing: "-0.02em" },
  // Scores
  section: { marginBottom: "22px" },
  sectionTitle: { fontSize: "0.62rem", textTransform: "uppercase", letterSpacing: "0.12em", color: "rgba(255,255,255,0.32)", marginBottom: "12px", fontWeight: "600" },
  scoreList: { display: "flex", flexDirection: "column", gap: "10px" },
  scoreRow: { display: "flex", alignItems: "center", gap: "10px" },
  scoreLabel: { fontSize: "0.7rem", color: "rgba(255,255,255,0.45)", width: "68px", flexShrink: 0 },
  scoreTrack: { flex: 1, height: "3px", background: "rgba(255,255,255,0.07)", borderRadius: "4px", overflow: "hidden" },
  scoreBar: { height: "100%", borderRadius: "4px" },
  scoreValue: { fontSize: "0.78rem", fontWeight: "700", fontFamily: "'Courier New', monospace", width: "28px", textAlign: "right", flexShrink: 0 },
  // Coach
  coachCard: { background: "rgba(96,165,250,0.05)", border: "1px solid rgba(96,165,250,0.18)", borderRadius: "16px", padding: "16px", marginBottom: "14px" },
  coachHeader: { display: "flex", alignItems: "center", gap: "8px", marginBottom: "11px" },
  coachTitle: { fontSize: "0.67rem", textTransform: "uppercase", letterSpacing: "0.12em", color: "#60a5fa", fontWeight: "700", flex: 1 },
  coachVersion: { fontSize: "0.58rem", color: "rgba(255,255,255,0.22)", fontFamily: "'Courier New', monospace" },
  coachReasoning: { fontSize: "0.85rem", lineHeight: "1.68", color: "rgba(255,255,255,0.78)", fontFamily: "Georgia, 'Times New Roman', serif", fontStyle: "italic", margin: "0 0 11px" },
  priorityBox: { display: "flex", alignItems: "flex-start", gap: "7px", background: "rgba(245,158,11,0.07)", border: "1px solid rgba(245,158,11,0.18)", borderRadius: "10px", padding: "9px 11px", marginBottom: "9px" },
  priorityText: { fontSize: "0.76rem", color: "rgba(255,255,255,0.68)", lineHeight: "1.5", margin: 0 },
  coachComposition: { fontSize: "0.75rem", color: "rgba(255,255,255,0.44)", lineHeight: "1.6", margin: 0, whiteSpace: "pre-line" },
  // RAG
  ragCard: { background: "rgba(167,139,250,0.05)", border: "1px solid rgba(167,139,250,0.18)", borderRadius: "12px", padding: "13px", marginBottom: "22px" },
  ragHeader: { display: "flex", alignItems: "center", gap: "6px", marginBottom: "7px" },
  ragTitle: { fontSize: "0.62rem", textTransform: "uppercase", letterSpacing: "0.12em", color: "#a78bfa", fontWeight: "700" },
  ragText: { fontSize: "0.72rem", color: "rgba(255,255,255,0.42)", fontFamily: "'Courier New', monospace", lineHeight: "1.5", margin: 0 },
  // Spec Actions
  specActions: { display: "flex", gap: "11px" },
  swipeBtn: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: "7px", padding: "15px", borderRadius: "14px", border: "none", fontSize: "0.88rem", fontWeight: "700", cursor: "pointer", letterSpacing: "0.02em" },
  swipeBtnAccept: { background: "rgba(16,185,129,0.18)", border: "1px solid rgba(16,185,129,0.35)", color: "#10b981" },
  swipeBtnReject: { background: "rgba(248,113,113,0.18)", border: "1px solid rgba(248,113,113,0.35)", color: "#f87171" },
  // Zoom
  zoomModal: { position: "fixed", inset: 0, zIndex: 300, background: "#000", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", overflow: "hidden" },
  zoomCloseBtn: { position: "absolute", top: "calc(env(safe-area-inset-top, 16px) + 10px)", right: "15px", zIndex: 310, width: "42px", height: "42px", borderRadius: "50%", background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.18)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)" },
  zoomHud: { position: "absolute", top: "calc(env(safe-area-inset-top, 16px) + 10px)", left: "15px", display: "flex", alignItems: "center", gap: "7px", zIndex: 310 },
  zoomImage: { maxWidth: "100vw", maxHeight: "100vh", objectFit: "contain", display: "block" },
  zoomSpinner: { position: "absolute", width: "28px", height: "28px", border: "2.5px solid rgba(255,255,255,0.15)", borderTopColor: "#60a5fa", borderRadius: "50%" },
  zoomFooter: { position: "absolute", bottom: "calc(env(safe-area-inset-bottom, 14px) + 14px)", left: "15px", right: "15px", display: "flex", flexDirection: "column", gap: "3px" },
  zoomFilename: { fontSize: "0.77rem", fontWeight: "600", color: "rgba(255,255,255,0.55)" },
  zoomExif: { fontSize: "0.68rem", color: "rgba(255,255,255,0.3)", fontFamily: "'Courier New', monospace" },
};
