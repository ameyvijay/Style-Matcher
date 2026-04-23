/**
 * Antigravity Engine — ImageBridge
 * Triple-buffer pre-fetching with memory management and network-aware throttling.
 *
 * Priority Model:
 *   P1: 800px WebP proxy  → next 3 cards (always fetched)
 *   P2: 1200px HQ preview → current card + next card (unless throttled)
 *   P3: Full-res / RAW    → only on explicit zoom trigger (300ms delay gate)
 *
 * Memory Management:
 *   - Object URLs are revoked when a card exits the 5-card buffer window.
 *   - Prevents heap exhaustion during 1000+ photo sessions.
 */

"use client";

import { useEffect, useRef, useCallback, useState } from "react";

// ── Constants ─────────────────────────────────────────────────────────
const P1_WINDOW   = 3;   // Prefetch 800px proxies for next N cards
const P2_WINDOW   = 2;   // Prefetch 1200px HQ for top N cards
const BUFFER_SIZE = 5;   // Max cards to hold in the object URL cache
const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();

// ── Helpers ───────────────────────────────────────────────────────────
function getProxyUrl(photo, size) {
  // If the photo already has a signed cloud URL, use it directly.
  if (photo.rlhf_url) return photo.rlhf_url;
  // Otherwise assume the backend serves the static file locally.
  const sourcePath = photo.original_path || photo.filepath || photo.url;
  if (sourcePath && typeof sourcePath === 'string' && sourcePath.startsWith('/')) {
    // Use the custom proxy for absolute paths to bypass project-root constraints
    return `${BASE_URL}/api/media?path=${encodeURIComponent(sourcePath)}&size=${size}`;
  }
  return sourcePath || null;
}

async function fetchAsObjectURL(url, priority = "auto") {
  if (!url) return null;
  try {
    const res = await fetch(url, {
      // browser fetch priority hint (ignored in non-Chromium gracefully)
      priority,
      // use cache aggressively for repeat views
      cache: "force-cache",
    });
    if (!res.ok) return null;
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}

// ── Hook: useImageCache ───────────────────────────────────────────────
/**
 * @param {object[]} photos   - The full ordered photo queue from Firestore.
 * @param {number}   topIndex - Index of the card currently on top.
 * @param {string}   syncMode - "optimal" | "throttled" | "offline"
 *
 * @returns {{ getObjectURL, preloadZoom, revokeCard }}
 */
export function useImageCache(photos, topIndex, syncMode = "optimal") {
  // Map of photoId → { p1: objectURL|null, p2: objectURL|null, p3: objectURL|null }
  const cache = useRef(new Map());
  // Track in-flight fetches to prevent duplicate requests
  const inflight = useRef(new Set());

  const revoke = useCallback((photoId, level) => {
    const entry = cache.current.get(photoId);
    if (!entry) return;
    if (entry[level]) {
      URL.revokeObjectURL(entry[level]);
      entry[level] = null;
    }
    // If all levels null, drop the entry entirely
    if (!entry.p1 && !entry.p2 && !entry.p3) {
      cache.current.delete(photoId);
    }
  }, []);

  // Revoke everything for a photo that has left the buffer
  const revokeCard = useCallback((photoId) => {
    const entry = cache.current.get(photoId);
    if (!entry) return;
    ["p1", "p2", "p3"].forEach((lvl) => {
      if (entry[lvl]) URL.revokeObjectURL(entry[lvl]);
    });
    cache.current.delete(photoId);
  }, []);

  // Prefetch a single level if not already done/in-flight
  const prefetchLevel = useCallback(
    async (photo, level, size, priority) => {
      const id = photo.id;
      const key = `${id}_${level}`;
      if (inflight.current.has(key)) return;
      const existing = cache.current.get(id);
      if (existing?.[level]) return; // already cached

      inflight.current.add(key);
      const url = getProxyUrl(photo, size);
      if (!url) {
        console.warn(`[useImageCache] No URL resolvable for photo ${id}`);
        inflight.current.delete(key);
        return;
      }
      
      const objectURL = await fetchAsObjectURL(url, priority);
      if (!objectURL) {
        console.error(`[useImageCache] Failed to fetch image: ${url}`);
      }
      inflight.current.delete(key);

      if (!objectURL) return;
      if (!cache.current.has(id)) {
        cache.current.set(id, { p1: null, p2: null, p3: null });
      }
      cache.current.get(id)[level] = objectURL;
    },
    []
  );

  // Main prefetch effect — runs when topIndex changes or syncMode changes
  useEffect(() => {
    const isThrottled = syncMode === "throttled";
    const isOffline = syncMode === "offline";

    for (let offset = 0; offset < BUFFER_SIZE; offset++) {
      const idx = topIndex + offset;
      if (idx >= photos.length) break;
      const photo = photos[idx];

      // P1: 800px for first P1_WINDOW cards — always, even when throttled
      if (offset < P1_WINDOW) {
        prefetchLevel(
          photo,
          "p1",
          800,
          offset === 0 ? "high" : offset === 1 ? "high" : "low"
        );
      }

      // P2: 1200px for top P2_WINDOW cards — skip if throttled/offline
      if (!isThrottled && !isOffline && offset < P2_WINDOW) {
        prefetchLevel(photo, "p2", 1200, offset === 0 ? "high" : "low");
      }
      // P3: Full-res — never prefetched here; triggered on demand via preloadZoom()
    }

    // Memory management: evict cards outside the buffer window
    const validIds = new Set(
      photos.slice(topIndex, topIndex + BUFFER_SIZE).map((p) => p.id)
    );
    for (const id of cache.current.keys()) {
      if (!validIds.has(id)) {
        revokeCard(id);
      }
    }
  }, [topIndex, photos, syncMode, prefetchLevel, revokeCard]);

  // Public: get the best available cached URL for a card
  const getObjectURL = useCallback((photoId) => {
    const entry = cache.current.get(photoId);
    if (!entry) return null;
    // Return highest quality available
    return entry.p2 || entry.p1 || null;
  }, []);

  // Public: triggered on zoom intent (200ms hold guard is in SwipeCard)
  const preloadZoom = useCallback(
    async (photo) => {
      if (syncMode === "throttled") return; // respect low-bandwidth mode
      prefetchLevel(photo, "p3", "full", "high");
    },
    [syncMode, prefetchLevel]
  );

  return { getObjectURL, preloadZoom, revokeCard };
}
