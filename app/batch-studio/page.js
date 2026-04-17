"use client";

import React, { useState, useEffect } from "react";
import { 
  Folder, Play, CheckCircle, XCircle, AlertCircle, 
  Loader2, Trash2, FileWarning, Search, ChevronRight, Terminal, StopCircle, RotateCcw
} from "lucide-react";
import ReactMarkdown from "react-markdown";

export default function BatchStudio() {
    const [targetFolder, setTargetFolder] = useState("");
    const [benchmarkFolder, setBenchmarkFolder] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState(null);
    const [logs, setLogs] = useState([]);
    const [sessionId] = useState(() => `sess_${Math.random().toString(36).substr(2, 9)}`);
    const [isRollingBack, setIsRollingBack] = useState(false);

    // Persist benchmark folder from global settings if available
    useEffect(() => {
        const saved = localStorage.getItem("benchmark_dir");
        if (saved) setBenchmarkFolder(saved);
        
        const lastTarget = localStorage.getItem("last_target_dir");
        if (lastTarget) setTargetFolder(lastTarget);
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
            const url = `${baseUrl}/api/batch-process-stream?target_folder=${encodeURIComponent(targetFolder)}&benchmark_folder=${encodeURIComponent(benchmarkFolder)}&session_id=${sessionId}`;
            
            // Immediate feedback
            setLogs([{ timestamp: Date.now()/1000, type: "sys", message: `Connecting to Antigravity Kernel at ${baseUrl}...` }]);
            
            const response = await fetch(url);
            
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || `Connection failed: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split("\n").filter(l => l.trim() !== "");

                for (const line of lines) {
                    try {
                        const event = JSON.parse(line);
                        setLogs(prev => [...prev, event]);
                        
                        if (event.type === "done") {
                            setResults({ metrics: event.data, mode: "batch" });
                            setIsProcessing(false);
                        }
                        if (event.type === "warn") setIsRollingBack(true);
                        if (event.type === "revert") setIsRollingBack(true);
                    } catch (e) {
                        console.error("Malformed log chunk", line);
                    }
                }
            }
        } catch (err) {
            console.error("Batch error:", err);
            setError(err.message);
            setIsProcessing(false);
        }
    };

    const stopBatch = async () => {
        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            await fetch(`${baseUrl}/api/stop-batch?session_id=${sessionId}`, { method: "POST" });
        } catch (err) {
            console.error("Stop request failed", err);
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
            const response = await fetch(`${baseUrl}/api/scan`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    target_folder: targetFolder,
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
                            <span style={{ fontSize: "1.2rem", fontWeight: "600" }}>Antigravity Engine v2.0 — Completed in {results.metrics?.processing_time || 0}s</span>
                        </div>

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
                                    <li style={{ color: "#ff8888" }}><strong>{results.mode === "scan_only" ? "Would Cull:" : "Moved to /Rejected:"}</strong> {results.metrics?.culled || 0}</li>
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
                                        📂 <strong>/Rejected/</strong> — Culled photos (moved, not deleted)<br/>
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
