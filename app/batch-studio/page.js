"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Folder, Loader2, Play, CheckCircle, BrainCircuit, XCircle, FileWarning } from "lucide-react";
import ReactMarkdown from 'react-markdown';

export default function BatchStudio() {
    const [targetFolder, setTargetFolder] = useState("");
    const [benchmarkFolder, setBenchmarkFolder] = useState("");
    
    const [isProcessing, setIsProcessing] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState(null);
    const [apiKey, setApiKey] = useState("");

    useEffect(() => {
        const key = localStorage.getItem("gemini_api_key") || localStorage.getItem("gemini_key");
        if (key) setApiKey(key);
        const benchStr = localStorage.getItem("benchmark_folder");
        if (benchStr) setBenchmarkFolder(benchStr);
    }, []);

    const runBatch = async () => {
        if (!targetFolder) {
            setError("You must provide an absolute path for the Target Folder.");
            return;
        }

        setIsProcessing(true);
        setError(null);
        setResults(null);
        
        try {
            const currentProvider = localStorage.getItem("ai_provider") || "gemini";
            const currentOllamaUrl = localStorage.getItem("ollama_url") || "http://host.docker.internal:11434";
            const currentOllamaModel = localStorage.getItem("ollama_model") || "gemma4:e4b";

            // Native CORS safe call to the Dockerized Python engine resolving at 8000
            const backendUrl = "http://localhost:8000/api/batch-process";
            
            const response = await fetch(backendUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    target_folder: targetFolder.trim(),
                    benchmark_folder: benchmarkFolder.trim() || null,
                    api_key: apiKey || null,
                    provider: currentProvider,
                    ollama_url: currentOllamaUrl,
                    ollama_model: currentOllamaModel
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || "Backend Processing Error");
            }
            
            setResults(data);
        } catch (err) {
            setError(err.message || "Ensure the Docker container is running and port 8000 is exposed.");
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <main className="container" style={{ padding: "4rem 2rem" }}>
            <div style={{ marginBottom: "2rem" }}>
                <Link href="/" className="btn btn-secondary" style={{ padding: "0.5rem 1rem" }}>
                    <ArrowLeft size={16} /> Back to Dashboard
                </Link>
            </div>

            <div style={{ textAlign: "center", marginBottom: "3rem" }}>
                <h1 style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.75rem" }}>
                    <BrainCircuit size={40} color="var(--accent-base)" />
                    AI Batch Studio & Photo Coach
                </h1>
                <p>Run massive offline parallel processing logic analyzing EXIFs, OpenCV optics, and aesthetic algorithms to auto-cull your worst photos natively.</p>
            </div>

            <div className="glass-panel" style={{ padding: "3rem", display: "flex", flexDirection: "column", gap: "2rem", maxWidth: "800px", margin: "0 auto" }}>
                
                {error && (
                    <div style={{ padding: "1rem", backgroundColor: "rgba(255,50,50,0.1)", border: "1px solid rgba(255,50,50,0.3)", borderRadius: "8px", color: "#ff8888", display: "flex", gap: "1rem", alignItems: "center" }}>
                        <XCircle size={24} /> {error}
                    </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <label style={{ fontWeight: "bold", fontSize: "1.2rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
                        <Folder size={20} color="var(--accent-hover)"/>
                        Target Directory Path (Absolute)
                    </label>
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginTop: "-0.5rem" }}>
                        Example: <code>/Users/Amey/Desktop/MyPhotos</code>
                    </p>
                    <input 
                        type="text" 
                        value={targetFolder}
                        onChange={(e) => setTargetFolder(e.target.value)}
                        placeholder="/Absolute/Path/To/Your/Directory"
                        style={{ padding: "1rem", borderRadius: "8px", background: "rgba(0,0,0,0.3)", border: "1px solid var(--glass-border)", color: "#fff", width: "100%", fontSize: "1rem" }}
                    />
                </div>

                {!isProcessing && !results && (
                    <button onClick={runBatch} className="btn btn-primary" style={{ padding: "1.2rem", fontSize: "1.2rem", display: "flex", justifyContent: "center", marginTop: "1rem" }}>
                        <Play size={22} fill="white" /> Execute AI Batch Engine
                    </button>
                )}

                {isProcessing && (
                    <div style={{ padding: "2rem", display: "flex", flexDirection: "column", alignItems: "center", gap: "1.5rem", border: "1px solid var(--glass-border)", borderRadius: "12px", background: "rgba(0,0,0,0.2)" }}>
                        <Loader2 className="loader" size={48} color="var(--accent-hover)" />
                        <h3>Secure Culling Engine Running...</h3>
                        <p style={{ color: "var(--text-secondary)", textAlign: "center" }}>
                            Transpiling RAW data streams. Evaluating perceptual block hashes for duplicates.<br/>
                            Running OpenCV Laplacian operators to detect out-of-focus optics...
                        </p>
                    </div>
                )}

                {results && !isProcessing && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "2rem", animation: "fadeIn 0.5s ease-out" }}>
                        <div style={{ display: "flex", padding: "1rem", background: "rgba(0,255,100,0.1)", border: "1px solid rgba(0,255,100,0.3)", borderRadius: "8px", gap: "1rem", alignItems: "center", color: "#aaffaa" }}>
                            <CheckCircle size={30} /> 
                            <span style={{ fontSize: "1.2rem", fontWeight: "600" }}>Directory Processing Concluded Succesfully</span>
                        </div>

                        <div className="grid-2">
                            <div className="glass-panel" style={{ padding: "1.5rem", background: "rgba(255,255,255,0.05)" }}>
                                <h3>Data Metrics</h3>
                                <ul style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "1rem" }}>
                                    <li><strong>Total Scanned:</strong> {results.metrics.total_scanned}</li>
                                    <li style={{ color: "#aaffaa" }}><strong>Accepted & Moved:</strong> {results.metrics.accepted}</li>
                                    <li style={{ color: "#ff8888" }}><strong>Duplicates Destroyed:</strong> {results.metrics.rejected_duplicates}</li>
                                    <li style={{ color: "#ff8888" }}><strong>Blur Out-of-Focus Rejected:</strong> {results.metrics.rejected_blur}</li>
                                </ul>
                            </div>
                            
                            <div className="glass-panel" style={{ padding: "1.5rem", background: "rgba(255,255,255,0.05)" }}>
                                <h3>File System Status</h3>
                                <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginTop: "1rem", lineHeight: 1.6 }}>
                                    The script safely performed file system operations directly formatting your explicit directory. 
                                    Valid formats successfully bypassed the physical barriers and landed in <code>/Creatively edited by AI</code>.
                                    Failed architectures landed in <code>/Rejected</code>.
                                </p>
                            </div>
                        </div>

                        {results.coaching_report && (
                            <div className="glass-panel" style={{ padding: "2rem", border: "1px solid var(--accent-hover)" }}>
                                <h2 style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "1rem" }}>
                                    <FileWarning size={28} color="#FFD700" /> AI Coach Assessment (Sony a6400)
                                </h2>
                                <div style={{ lineHeight: "1.8", color: "var(--text-secondary)" }}>
                                    <ReactMarkdown>{results.coaching_report}</ReactMarkdown>
                                </div>
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
