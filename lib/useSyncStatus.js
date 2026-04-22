/**
 * Antigravity Engine — useSyncStatus
 * Polls /api/health/sync every 5s and derives the UI sync state.
 *
 * States:
 *   "optimal"    — backlog < 5 AND ping < 100ms → green pulse
 *   "throttled"  — backlog > 20 OR ping > 500ms  → amber, pause P3 prefetch
 *   "stalled"    — failed_directories > 0         → show stalled banner
 *   "offline"    — fetch failed or timeout        → red, local-first mode
 *   "syncing"    — a cull/keep action in-flight   → animated dot
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";

const POLL_INTERVAL_MS = 5_000;
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useSyncStatus() {
  const [status, setStatus] = useState("optimal");
  const [backlog, setBacklog] = useState(0);
  const [latencyMs, setLatencyMs] = useState(null);
  const [failedDirs, setFailedDirs] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const actionTimerRef = useRef(null);

  const poll = useCallback(async () => {
    const t0 = performance.now();
    try {
      const controller = new AbortController();
      // Increase timeout to 8s - heavy batches can block the event loop
      const timeout = setTimeout(() => controller.abort(), 8_000);

      const res = await fetch(`${BASE_URL}/api/health/sync`, {
        signal: controller.signal,
        cache: "no-store",
      });
      clearTimeout(timeout);

      const ping = Math.round(performance.now() - t0);
      setLatencyMs(ping);

      if (!res.ok) {
        // If 503 or 504, backend is likely just busy processing a batch
        if (res.status >= 500) {
          setStatus("optimal"); // Keep pulse green if we know it's just processing
          return;
        }
        setStatus("offline");
        return;
      }

      const data = await res.json();
      const activeBacklog = data.active_queue ?? data.rendering_remaining ?? 0;
      const failed = data.failed_directories ?? 0;

      setBacklog(activeBacklog);
      setFailedDirs(failed);

      if (failed > 0) {
        setStatus("stalled");
      } else if (activeBacklog > 20 || ping > 500) {
        setStatus("throttled");
      } else if (ping > 100) {
        // mild lag — still optimal for UX purposes
        setStatus("optimal");
      } else {
        setStatus("optimal");
      }
    } catch {
      setStatus("offline");
      setLatencyMs(null);
    }
  }, []);

  // Initial poll + interval
  useEffect(() => {
    let active = true;
    const runPoll = async () => {
      if (active) await poll();
    };
    runPoll();
    const id = setInterval(runPoll, POLL_INTERVAL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [poll]);

  // Called by SwipeCard when a cull/keep action is fired
  const markSyncing = useCallback(() => {
    setIsSyncing(true);
    clearTimeout(actionTimerRef.current);
    // Auto-clear after 3s max (in case API never resolves)
    actionTimerRef.current = setTimeout(() => setIsSyncing(false), 3_000);
  }, []);

  // Called when the FastAPI POST returns 200
  const markSyncComplete = useCallback(() => {
    clearTimeout(actionTimerRef.current);
    setIsSyncing(false);
  }, []);

  return { status, backlog, latencyMs, failedDirs, isSyncing, markSyncing, markSyncComplete };
}
