"use client";

import React, { useState, useEffect } from "react";
import { 
  Folder, Play, CheckCircle, XCircle, AlertCircle, AlertTriangle, RefreshCw, 
  Loader2, Trash2, FileWarning, Search, ChevronRight, Terminal, StopCircle, RotateCcw
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useBatch } from "../../components/BatchContext";

// ── Vitals Mini-Bar Component ──────────────────────────────────────────
const VitalsBar = ({ vitals, cpu, models }) => {
    const { Cpu, HardDrive, Thermometer, Database, ScanLine, Eye, Sparkles, MessageSquare } = require("lucide-react");
    
    const experts = [
        { id: "laplacian_v2", label: "Focus", Icon: ScanLine },
        { id: "nima_v1",      label: "Aesthetics", Icon: Eye },
        { id: "clip_vit_b32", label: "Semantics", Icon: Sparkles },
        { id: "ollama_vlm",   label: "VLM", Icon: MessageSquare }
    ];

    return (
        <div style={{ marginBottom: "1.5rem" }}>
            {/* Row 1: Hardware Vitals */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem", marginBottom: "0.75rem" }}>
                <div style={hwStyles.card}>
                    <Cpu size={14} color="#60a5fa" />
                    <span style={hwStyles.label}>CPU</span>
                    <span style={hwStyles.value}>{cpu ?? "—"}%</span>
                </div>
                <div style={hwStyles.card}>
                    <HardDrive size={14} color="#a78bfa" />
                    <span style={hwStyles.label}>VRAM</span>
                    <span style={hwStyles.value}>{vitals?.memory?.used_gb ?? "—"} GB</span>
                </div>
                <div style={{ ...hwStyles.card, borderLeft: vitals?.thermal === "Throttled" ? "3px solid #f87171" : "none" }}>
                    <Thermometer size={14} color={vitals?.thermal === "Throttled" ? "#f87171" : "#fbbf24"} />
                    <span style={hwStyles.label}>Thermal</span>
                    <span style={{ ...hwStyles.value, color: vitals?.thermal === "Throttled" ? "#f87171" : "#fff" }}>{vitals?.thermal ?? "Nominal"}</span>
                </div>
                <div style={hwStyles.card}>
                    <Database size={14} color="#10b981" />
                    <span style={hwStyles.label}>Disk</span>
                    <span style={hwStyles.value}>{vitals?.disk?.free_gb ?? "—"} GB</span>
                </div>
            </div>

            {/* Row 2: Model Expert Status */}
            <div style={{ display: "flex", gap: "0.75rem", padding: "0 0.25rem" }}>
                {experts.map(exp => {
                    const isActive = models?.[exp.id]?.status === "Healthy";
                    return (
                        <div key={exp.id} style={{ 
                            display: "flex", alignItems: "center", gap: "0.4rem", padding: "0.3rem 0.65rem",
                            borderRadius: "100px", background: isActive ? "rgba(16,185,129,0.12)" : "rgba(255,255,255,0.03)",
                            border: `1px solid ${isActive ? "rgba(16,185,129,0.3)" : "rgba(255,255,255,0.08)"}`,
                            transition: "all 0.3s ease"
                        }}>
                            <exp.Icon size={12} color={isActive ? "#10b981" : "rgba(255,255,255,0.2)"} />
                            <span style={{ fontSize: "0.6rem", fontWeight: "700", color: isActive ? "#10b981" : "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                                {exp.label}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

const hwStyles = {
    card: {
        display: "flex", alignItems: "center", gap: "0.6rem", padding: "0.6rem 0.8rem",
        background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "10px"
    },
    label: { fontSize: "0.65rem", color: "rgba(255,255,255,0.35)", fontWeight: "600", flex: 1 },
    value: { fontSize: "0.8rem", fontWeight: "800", color: "#fff", fontFamily: "monospace" }
};

// 1. The Observability Banner Component (Glassmorphism Styled)
// 1. The Observability Banner Component (GA Hybrid-Cloud)
const SyncAlertBanner = ({ health, apiError }) => {
    // DISCONNECTED STATE: Red / High Urgency
    if (apiError || (health && health.status === "disconnected")) {
        const isNetworkError = apiError;
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

        return (
            <div style={{ 
                background: "rgba(127, 29, 29, 0.4)", 
                backdropFilter: "blur(12px)", 
                border: "1px solid rgba(239, 68, 68, 0.5)", 
                color: "#fecaca", 
                padding: "1.25rem", 
                borderRadius: "12px", 
                display: "flex", 
                alignItems: "center", 
                marginBottom: "1.5rem",
                boxShadow: "0 8px 32px rgba(0, 0, 0, 0.4)" 
            }}>
                <XCircle style={{ width: "24px", height: "24px", marginRight: "1rem", color: "#f87171", flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                    <h3 style={{ fontWeight: "bold", color: "#fecaca", margin: 0 }}>🚨 Control Plane Disconnected</h3>
                    <p style={{ fontSize: "0.85rem", opacity: 0.9, margin: 0 }}>
                        {isNetworkError 
                            ? `Network Error: Cannot reach Antigravity Engine at ${baseUrl}. Ensure Ngrok is running on the Mac Mini.` 
                            : "Firestore Error: The Mac Mini reached the cloud but failed to authenticate. Check the Service Account JSON."}
                    </p>
                    <p style={{ fontSize: "0.7rem", marginTop: "0.4rem", opacity: 0.7, fontStyle: "italic" }}>
                        Diagnostic: API returned {isNetworkError ? "Connection Refused (0)" : "Logic Error (200/500)"}.
                    </p>
                </div>
            </div>
        );
    }

    if (!health || health.rendering_remaining === 0) {
        return null; // Hidden when healthy and idle
    }

    return (
        <div style={{ width: "100%", marginBottom: "1.5rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {/* RENDERING STATE: Frosted Amber / Progress */}
            {health.rendering_remaining > 0 && (
                <div style={{ 
                    background: "rgba(120, 53, 15, 0.4)", 
                    backdropFilter: "blur(12px)", 
                    border: "1px solid rgba(245, 158, 11, 0.5)", 
                    color: "#fef3c7", 
                    padding: "1.25rem", 
                    borderRadius: "12px", 
                    display: "flex", 
                    alignItems: "center", 
                    boxShadow: "0 8px 32px rgba(0, 0, 0, 0.4)"
                }}>
                    <AlertTriangle style={{ width: "24px", height: "24px", marginRight: "1rem", color: "#fbbf24", flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                        <h3 style={{ fontWeight: "bold", color: "#fef3c7", margin: 0 }}>⚙️ Rendering Masters: {health.rendering_remaining} Remaining</h3>
                        <p style={{ fontSize: "0.85rem", opacity: 0.9, margin: 0 }}>
                            Mac Mini M4 GPU is fulfilling Stage 9 realization requests from Firestore.
                        </p>
                    </div>
                    <RefreshCw className="animate-spin" style={{ width: "20px", height: "20px", marginLeft: "auto", color: "#fbbf24", opacity: 0.6 }} />
                    <style>{`
                        @keyframes spin {
                            from { transform: rotate(0deg); }
                            to { transform: rotate(360deg); }
                        }
                        .animate-spin {
                            animation: spin 2s linear infinite;
                        }
                    `}</style>
                </div>
            )}
        </div>
    );
};

export default function BatchStudio() {
    const { 
        targetFolder, setTargetFolder,
        isProcessing, setIsProcessing,
        results, setResults,
        error, setError,
        logs, setLogs,
        sessionId, setSessionId,
        isRollingBack, setIsRollingBack
    } = useBatch();

    const [benchmarkFolder, setBenchmarkFolder] = useState("");
    const [syncHealth, setSyncHealth] = useState(null);
    const [apiError, setApiError] = useState(false);
    const [vitals, setVitals] = useState(null);
    const [cpu, setCpu] = useState(0);
    const [modelHealth, setModelHealth] = useState({});
    const [showPostRunLogs, setShowPostRunLogs] = useState(false);

    // 2. The Telemetry Hook (Hardware Vitals Polling)
    useEffect(() => {
        let isMounted = true;
        const fetchVitals = async () => {
            try {
                const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                const [telRes, vitRes] = await Promise.all([
                    fetch(`${baseUrl}/api/admin/telemetry`),
                    fetch(`${baseUrl}/api/admin/vitals`)
                ]);
                
                if (isMounted) {
                    if (telRes.ok) {
                        const telData = await telRes.json();
                        setCpu(telData.system?.cpu_usage);
                        setModelHealth(telData.models || {});
                        setApiError(false);
                    }
                    if (vitRes.ok) {
                        const vitData = await vitRes.json();
                        setVitals(vitData);
                    }
                }
            } catch (error) {
                if (isMounted) console.warn("Vitals poll failed.");
            }
        };

        fetchVitals();
        const intervalId = setInterval(fetchVitals, 5000); 

        return () => {
            isMounted = false;
            clearInterval(intervalId);
        };
    }, []);

    // 3. The Sync Health Hook
    useEffect(() => {
        let isMounted = true;
        const fetchSyncHealth = async () => {
            try {
                const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                const response = await fetch(`${baseUrl}/api/health/sync`);
                if (isMounted && response.ok) {
                    const data = await response.json();
                    setSyncHealth(data);
                }
            } catch (error) {}
        };
        fetchSyncHealth();
        const id = setInterval(fetchSyncHealth, 10000);
        return () => { isMounted = false; clearInterval(id); };
    }, []);

    const handleFolderPicker = async (setter, key) => {
        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${baseUrl}/api/pick-folder`);
            if (!res.ok) {
                const errData = await res.json();
                console.log("Folder picker:", errData.detail);
                return;
            }
            const data = await res.json();
            setter(data.path);
            if (key) localStorage.setItem(key, data.path);
        } catch (err) {
            console.error("Folder picker failed:", err);
        }
    };

    const runBatch = async () => {
        if (!targetFolder) {
            setError("Please specify a target folder.");
            return;
        }
        
        setError(null);
        setIsProcessing(true);
        setIsRollingBack(false);
        setResults(null);
        setLogs([]);
        localStorage.setItem("last_target_dir", targetFolder);

        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const url = `${baseUrl}/api/batch-process`;
            
            // Immediate feedback
            setLogs([{ timestamp: Date.now()/1000, type: "sys", message: `Connecting to Antigravity Kernel at ${baseUrl}...` }]);
            
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    target_folder: targetFolder, 
                    benchmark_folder: benchmarkFolder, 
                    session_id: sessionId 
                })
            });
            
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Connection failed: ${response.statusText}`);
            }
            
            // Fire-and-forget: the polling hook takes over from here
            const data = await response.json();
            if (data.status === "error") {
                throw new Error(data.message);
            }
            // isProcessing stays true — polling useEffect will handle completion
        } catch (err) {
            console.error("Batch error:", err);
            setError(err.message);
            setIsProcessing(false);
        }
    };

    const stopBatch = async () => {
        if (!sessionId) return;
        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            await fetch(`${baseUrl}/api/stop-batch?session_id=${sessionId}`, { method: "POST" });
            console.log("Stop request sent for session:", sessionId);
        } catch (err) {
            console.warn("Stop request failed (backend likely busy):", err);
        }
    };

    const runScan = async () => {
        if (!targetFolder) {
            setError("Please specify a target folder.");
            return;
        }
        
        setError(null);
        setIsProcessing(true);
        setResults(null);
        localStorage.setItem("last_target_dir", targetFolder);

        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            setLogs([{ timestamp: Date.now()/1000, type: "sys", message: "Starting Scan Only mode..." }]);
            
            const response = await fetch(`${baseUrl}/api/scan`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    target_folder: targetFolder,
                    session_id: sessionId
                })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Scan failed");
            }

            const data = await response.json();
            setResults(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsProcessing(false);
        }
    };

    const onDrop = (e, setter) => {
        e.preventDefault();
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            // Note: In Chrome/Edge, this is often a relative path. 
            // The user should paste absolute paths for the Mac Mini backend.
            console.log("File dropped:", files[0]);
        }
    };

    return (
        <main className="container" style={{ padding: "2rem", maxWidth: "1000px" }}>
            <div className="glass-panel" style={{ padding: "3rem", display: "flex", flexDirection: "column", gap: "2rem" }}>
                <header style={{ textAlign: "center", marginBottom: "1rem" }}>
                    <h1 style={{ fontSize: "2.5rem", fontWeight: "800", background: "linear-gradient(to right, #fff, #888)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                        Antigravity Batch Studio
                    </h1>
                    <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
                        AI Photo Culling & Enhancement Engine v2.0
                    </p>
                </header>

                {/* Real-time Hardware Vitals (Ported from Telemetry) */}
                <VitalsBar vitals={vitals} cpu={cpu} models={modelHealth} />

                {/* Mount the banner at the very top of the layout */}
                <SyncAlertBanner health={syncHealth} />

                {error && (
                    <div className="error-box" style={{ padding: "1rem", borderRadius: "8px", background: "rgba(255,0,0,0.1)", border: "1px solid rgba(255,0,0,0.3)", display: "flex", gap: "1rem", alignItems: "center", color: "#ff8888" }}>
                        <AlertCircle /> {error}
                    </div>
                )}

                <div className="input-group" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: "600" }}>
                        <Folder size={18} /> Target Directory Path (Absolute)
                    </label>
                    <div style={{ display: "flex", gap: "1rem" }}>
                        <input 
                            type="text" 
                            className="input-field"
                            placeholder="Example: /Users/shivamagent/Desktop/MyPhotos"
                            value={targetFolder}
                            onChange={(e) => setTargetFolder(e.target.value)}
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={(e) => onDrop(e, setTargetFolder)}
                            style={{ flex: 1 }}
                            disabled={isProcessing}
                        />
                    </div>
                    <p style={{ fontSize: "0.75rem", color: "#888", fontStyle: "italic" }}>
                        <strong>Pro-Tip:</strong> Grab any folder in Finder and <strong>drop it directly</strong> into the box above to capture the path. (Browse dialog disabled in background worker mode).
                    </p>
                </div>

                {!isProcessing && !results && (
                    <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
                        <button onClick={runScan} className="btn btn-secondary" style={{ padding: "1.2rem", fontSize: "1.1rem", display: "flex", justifyContent: "center", flex: 1, border: "1px solid rgba(255,255,255,0.2)" }}>
                            🔍 Scan Only (Read-Only)
                        </button>
                        <button onClick={runBatch} className="btn btn-primary" style={{ padding: "1.2rem", fontSize: "1.1rem", display: "flex", justifyContent: "center", flex: 1 }}>
                            <Play size={22} fill="white" /> Execute Full Pipeline
                        </button>
                    </div>
                )}

                {isProcessing && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                        <div style={{ 
                            background: "#0a0a0a", 
                            border: "1px solid #333", 
                            borderRadius: "12px", 
                            padding: "1rem", 
                            height: "400px", 
                            overflowY: "auto", 
                            fontFamily: "'SF Mono', monospace", 
                            fontSize: "0.85rem",
                            boxShadow: "inset 0 4px 12px rgba(0,0,0,0.5)"
                        }}>
                             <div style={{ display: "flex", alignItems: "center", gap: "1rem", borderBottom: "1px solid #222", paddingBottom: "0.75rem", marginBottom: "0.75rem", position: "sticky", top: 0, background: "#0a0a0a", zIndex: 10 }}>
                                <Terminal size={16} color="#4ade80" />
                                <span style={{ color: "#888", fontWeight: "600", letterSpacing: "1px" }}>ANTIGRAVITY_KERNEL_OUTPUT</span>
                                <div style={{ marginLeft: "auto", display: "flex", gap: "0.5rem" }}>
                                    {!isRollingBack && (
                                        <button 
                                            onClick={stopBatch}
                                            style={{ background: "#4e1d1d", color: "#f87171", border: "1px solid #7f1d1d", padding: "0.3rem 0.8rem", borderRadius: "4px", fontSize: "0.75rem", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.4rem" }}
                                        >
                                            <StopCircle size={14} /> Abort Run
                                        </button>
                                    )}
                                </div>
                             </div>

                             {logs.map((log, i) => {
                                 const isLast = i === logs.length - 1;
                                 let color = "#fff";
                                 let icon = null;
                                 
                                 if (log.type === "sys") color = "#0ea5e9";
                                 if (log.type === "progress") color = "#4ade80";
                                 if (log.type === "warn") color = "#fb923c";
                                 if (log.type === "error") color = "#f87171";
                                 if (log.type === "revert") color = "#a78bfa";

                                 return (
                                     <div key={i} style={{ 
                                         display: "flex", 
                                         gap: "1rem", 
                                         padding: "0.2rem 0", 
                                         borderLeft: isLast ? "2px solid var(--accent-hover)" : "none",
                                         paddingLeft: isLast ? "0.5rem" : 0
                                     }}>
                                         <span style={{ color: "#444", minWidth: "50px" }}>{new Date(log.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                                         <span style={{ color }}>
                                             {log.type === "revert" && <RotateCcw size={12} style={{ marginRight: '5px' }} />}
                                             {log.message}
                                             {log.data?.tier && (
                                                <span style={{ marginLeft: "10px", color: "#666" }}>
                                                    [Sharp: {log.data.sharpness}% | Aesthetic: {log.data.aesthetic}%]
                                                </span>
                                             )}
                                         </span>
                                     </div>
                                 );
                             })}
                             {isProcessing && !isRollingBack && <div className="pulsing-cursor">_</div>}
                        </div>
                        
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 1rem" }}>
                             <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                                <Loader2 className="loader" size={20} color="var(--accent-hover)" />
                                <span style={{ fontSize: "0.9rem", color: "#888" }}>
                                    {isRollingBack ? "Executing Safe Rollback..." : "Engine v2.1 Processing..."}
                                </span>
                             </div>
                             <div style={{ fontSize: "0.8rem", color: "#666" }}>Session ID: {sessionId}</div>
                        </div>
                    </div>
                )}

                {results && !isProcessing && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "2rem", animation: "fadeIn 0.5s ease-out" }}>
                        <div style={{ display: "flex", padding: "1rem", background: "rgba(0,255,100,0.1)", border: "1px solid rgba(0,255,100,0.3)", borderRadius: "8px", gap: "1rem", alignItems: "center", color: "#aaffaa" }}>
                            <CheckCircle size={30} /> 
                            <div style={{ flex: 1 }}>
                                <span style={{ fontSize: "1.2rem", fontWeight: "600", display: "block" }}>Antigravity Engine v2.1 — Completed in {results.metrics?.processing_time || 0}s</span>
                                <span style={{ fontSize: "0.8rem", opacity: 0.8 }}>All intelligence signals synchronized.</span>
                            </div>
                            <button 
                                onClick={() => setShowPostRunLogs(!showPostRunLogs)}
                                style={{ 
                                    background: "rgba(0,255,100,0.1)", 
                                    borderColor: "rgba(0,255,100,0.2)", 
                                    color: "#aaffaa",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "0.5rem",
                                    padding: "0.5rem 1rem",
                                    borderRadius: "6px",
                                    border: "1px solid",
                                    cursor: "pointer",
                                    fontSize: "0.85rem",
                                    fontWeight: "600",
                                    transition: "all 0.2s ease"
                                }}
                            >
                                <Terminal size={14} />
                                {showPostRunLogs ? "Hide Console" : "View Console Logs"}
                            </button>
                        </div>

                        {showPostRunLogs && (
                            <div style={{ 
                                background: "#0a0a0a", border: "1px solid #333", borderRadius: "12px", 
                                padding: "1rem", height: "300px", overflowY: "auto", 
                                fontFamily: "'SF Mono', monospace", fontSize: "0.85rem"
                            }}>
                                {logs.map((log, i) => (
                                    <div key={i} style={{ display: "flex", gap: "1rem", padding: "0.2rem 0" }}>
                                        <span style={{ color: "#444" }}>{new Date(log.timestamp * 1000).toLocaleTimeString()}</span>
                                        <span style={{ color: log.type === "error" ? "#f87171" : "#888" }}>{log.message}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Tier Breakdown Cards */}
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "1rem" }}>
                            <div className="glass-panel" style={{ padding: "1.2rem", textAlign: "center", borderLeft: "3px solid #4ade80" }}>
                                <div style={{ fontSize: "2rem", fontWeight: "800", color: "#4ade80" }}>{results.metrics?.portfolio || 0}</div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>🏆 Portfolio</div>
                            </div>
                            <div className="glass-panel" style={{ padding: "1.2rem", textAlign: "center", borderLeft: "3px solid #facc15" }}>
                                <div style={{ fontSize: "2rem", fontWeight: "800", color: "#facc15" }}>{results.metrics?.keepers || 0}</div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>✅ Keeper</div>
                            </div>
                            <div className="glass-panel" style={{ padding: "1.2rem", textAlign: "center", borderLeft: "3px solid #fb923c" }}>
                                <div style={{ fontSize: "2rem", fontWeight: "800", color: "#fb923c" }}>{results.metrics?.review || 0}</div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>🔍 Review</div>
                            </div>
                            <div className="glass-panel" style={{ padding: "1.2rem", textAlign: "center", borderLeft: "3px solid #f87171" }}>
                                <div style={{ fontSize: "2rem", fontWeight: "800", color: "#f87171" }}>{results.metrics?.culled || 0}</div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>❌ Culled</div>
                            </div>
                            <div className="glass-panel" style={{ padding: "1.2rem", textAlign: "center", borderLeft: "3px solid #a78bfa" }}>
                                <div style={{ fontSize: "2rem", fontWeight: "800", color: "#a78bfa" }}>{results.metrics?.recoverable || 0}</div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>🔧 Recoverable</div>
                            </div>
                        </div>

                        {/* Processing Stats */}
                        <div className="grid-2">
                            <div className="glass-panel" style={{ padding: "1.5rem", background: "rgba(255,255,255,0.05)" }}>
                                <h3>Processing Summary</h3>
                                <ul style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "1rem" }}>
                                    <li><strong>Total Scanned:</strong> {results.metrics?.total_scanned || 0}</li>
                                    {results.mode !== "scan_only" && (
                                        <li style={{ color: "#aaffaa" }}><strong>Enhanced Master JPEGs:</strong> {results.metrics?.enhanced || 0}</li>
                                    )}
                                    {results.mode !== "scan_only" && (
                                        <li style={{ color: "#88ccff" }}><strong>AI Denoised:</strong> {results.metrics?.denoised || 0}</li>
                                    )}
                                    {(results.metrics?.recoverable || 0) > 0 && (
                                        <li style={{ color: "#a78bfa" }}><strong>🔧 Recoverable:</strong> {results.metrics?.recoverable} <em>(sharp but poorly exposed)</em></li>
                                    )}
                                </ul>
                            </div>
                            
                            {/* Scan mode: show file listing by tier */}
                            {results.mode === "scan_only" && results.file_listing && (
                                <div className="glass-panel" style={{ padding: "1.5rem", background: "rgba(255,255,255,0.05)" }}>
                                    <h3>📋 File Listing by Tier</h3>
                                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem", fontSize: "0.9rem", fontFamily: "monospace" }}>
                                        {results.file_listing.portfolio?.length > 0 && (
                                            <div>
                                                <div style={{ color: "#4ade80", fontWeight: "700", marginBottom: "0.3rem" }}>🏆 PORTFOLIO ({results.file_listing.portfolio.length}) — Enhance these:</div>
                                                {results.file_listing.portfolio.map((f, i) => <div key={i} style={{ paddingLeft: "1.5rem", color: "#ccc" }}>{f}</div>)}
                                            </div>
                                        )}
                                        {results.file_listing.keeper?.length > 0 && (
                                            <div>
                                                <div style={{ color: "#facc15", fontWeight: "700", marginBottom: "0.3rem" }}>✅ KEEPER ({results.file_listing.keeper.length}) — Enhance these:</div>
                                                {results.file_listing.keeper.map((f, i) => <div key={i} style={{ paddingLeft: "1.5rem", color: "#ccc" }}>{f}</div>)}
                                            </div>
                                        )}
                                        {results.file_listing.review?.length > 0 && (
                                            <div>
                                                <div style={{ color: "#fb923c", fontWeight: "700", marginBottom: "0.3rem" }}>🔍 REVIEW ({results.file_listing.review.length}) — Worth a second look:</div>
                                                {results.file_listing.review.map((f, i) => <div key={i} style={{ paddingLeft: "1.5rem", color: "#ccc" }}>{f}</div>)}
                                            </div>
                                        )}
                                        {results.file_listing.recoverable?.length > 0 && (
                                            <div>
                                                <div style={{ color: "#a78bfa", fontWeight: "700", marginBottom: "0.3rem" }}>🔧 RECOVERABLE ({results.file_listing.recoverable.length}) — Sharp, needs post-work:</div>
                                                {results.file_listing.recoverable.map((f, i) => <div key={i} style={{ paddingLeft: "1.5rem", color: "#ccc" }}>{f}</div>)}
                                            </div>
                                        )}
                                        {results.file_listing.cull?.length > 0 && (
                                            <div>
                                                <div style={{ color: "#f87171", fontWeight: "700", marginBottom: "0.3rem" }}>❌ CULL ({results.file_listing.cull.length}):</div>
                                                {results.file_listing.cull.map((f, i) => <div key={i} style={{ paddingLeft: "1.5rem", color: "#888" }}>{f}</div>)}
                                            </div>
                                        )}
                                    </div>
                                    <p style={{ fontSize: "0.8rem", color: "#888", marginTop: "1.5rem", fontStyle: "italic", borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "0.8rem" }}>
                                        💡 Move Portfolio + Keeper files to a new folder and run <strong>Execute Full Pipeline</strong> on it.
                                    </p>
                                </div>
                            )}

                            {/* Batch mode: show output locations */}
                            {results.mode !== "scan_only" && (
                                <div className="glass-panel" style={{ padding: "1.5rem", background: "rgba(255,255,255,0.05)" }}>
                                    <h3>Output Locations</h3>
                                    <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginTop: "1rem", lineHeight: 1.6 }}>
                                        📂 <strong>/Enhanced/</strong> — Master JPEGs developed from keepers<br/>
                                        📄 <strong>batch_report.json</strong> — AI Coach telemetry for LLM ingestion
                                    </p>
                                    <p style={{ fontSize: "0.8rem", color: "#888", marginTop: "1rem", fontStyle: "italic", borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "0.8rem" }}>
                                        Original RAW/JPEG files remain 100% untouched in the source folder.
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* AI Coach Report */}
                        {results.batch_coaching && (
                            <div className="glass-panel" style={{ padding: "2rem", border: "1px solid var(--accent-hover)" }}>
                                <h2 style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "1rem" }}>
                                    <FileWarning size={28} color="#FFD700" /> AI Photography Coach
                                </h2>
                                <pre style={{ lineHeight: "1.8", color: "var(--text-secondary)", whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "0.95rem" }}>
                                    {results.batch_coaching}
                                </pre>
                            </div>
                        )}
                        
                        <button onClick={() => setResults(null)} className="btn btn-secondary" style={{ marginTop: "1rem", alignSelf: "center" }}>
                            Process Another Directory
                        </button>
                    </div>
                )}
            </div>
            
            <style jsx>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </main>
    );
}
