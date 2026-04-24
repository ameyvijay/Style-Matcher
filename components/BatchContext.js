"use client";
import React, { createContext, useContext, useState, useEffect } from "react";

const BatchContext = createContext();

export function BatchProvider({ children }) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState(null);
  const [logs, setLogs] = useState([]);
  const [sessionId, setSessionId] = useState(() => {
    // Lazy initializer — runs only once, surviving re-renders and navigation
    if (typeof window !== "undefined") {
      const stored = sessionStorage.getItem("ag_session_id");
      if (stored) return stored;
      const id = `sess_${crypto.randomUUID()}`;
      sessionStorage.setItem("ag_session_id", id);
      return id;
    }
    return null;
  });
  const [error, setError] = useState(null);
  const [isRollingBack, setIsRollingBack] = useState(false);
  const [targetFolder, setTargetFolder] = useState("");

  // Remove the old useEffect for sessionId initialization
  // since it's now handled by the lazy initializer.

  useEffect(() => {
    if (isProcessing) return; // Already tracking something

    const checkActiveBatch = async () => {
      try {
        const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
        const res = await fetch(`${baseUrl}/api/batch/active`);
        if (!res.ok) return;
        const data = await res.json();
        
        if (data.active && data.session_id) {
          console.log("🔗 Found active background session:", data.session_id);
          setSessionId(data.session_id);
          setIsProcessing(true);
          // Don't clear logs, we want to see history of the silent run
        }
      } catch (err) {
        // Silent skip
      }
    };

    const intervalId = setInterval(checkActiveBatch, 3000); // Check for background runs every 3s
    checkActiveBatch();
    return () => clearInterval(intervalId);
  }, [isProcessing]);

  // Global Log Polling logic
  // This continues even if the user navigates away from the Batch Studio page!
  useEffect(() => {
    if (!isProcessing || !sessionId) return;
    
    let isMounted = true;
    // CRITICAL: On first run after refresh/reattach, linesSeen should be 0
    // so we get the full history of the background run. 
    // Subsequent polls will update this value.
    let linesSeen = 0; 
    let lastLogTime = Date.now();

    const poll = async () => {
      try {
        const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
        const res = await fetch(`${baseUrl}/api/logs/${sessionId}?after=${linesSeen}`);
        if (!res.ok) return;
        const data = await res.json();

        if (isMounted && data.logs.length > 0) {
          lastLogTime = Date.now();
          setLogs(prev => {
            if (linesSeen === 0) return data.logs; // First load: replace with history
            return [...prev, ...data.logs]; // Subsequent: append
          });
          linesSeen = data.total;

          // Check for rollback events
          const hasWarn = data.logs.some(l => l.type === "warn" || l.type === "revert");
          if (hasWarn) setIsRollingBack(true);

          // Check for completion via "done" event
          const doneEvent = data.logs.find(l => l.type === "done");
          if (doneEvent) {
            setResults({ metrics: doneEvent.data, mode: "batch" });
            setIsProcessing(false);
          }
        } else if (isMounted && isProcessing) {
          // Heartbeat: If no logs for 15s, show "Heavy processing" hint
          const idleTime = Date.now() - lastLogTime;
          if (idleTime > 15000 && idleTime < 16000) {
             setLogs(prev => [...prev, { 
               timestamp: Date.now()/1000, 
               type: "sys", 
               message: "⏳ Still working... (Large RAW file or VLM assessment in progress)" 
             }]);
          }
        }

        if (isMounted && data.batch_status === "completed" && !data.logs.find(l => l.type === "done")) {
          setIsProcessing(false);
        }
        if (isMounted && data.batch_status === "failed") {
          setError("Pipeline failed. Check terminal for details.");
          setIsProcessing(false);
        }
      } catch (err) {
        console.warn("Global Log poll error:", err);
      }
    };

    const intervalId = setInterval(poll, 500); // Faster polling (500ms)
    poll(); // Immediate poll
    return () => { 
      isMounted = false; 
      clearInterval(intervalId); 
    };
  }, [isProcessing, sessionId]);

  return (
    <BatchContext.Provider value={{
      isProcessing, setIsProcessing,
      results, setResults,
      logs, setLogs,
      sessionId, setSessionId,
      error, setError,
      isRollingBack, setIsRollingBack,
      targetFolder, setTargetFolder
    }}>
      {children}
    </BatchContext.Provider>
  );
}

export const useBatch = () => useContext(BatchContext);
