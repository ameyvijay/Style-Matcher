"use client";

import { useState, useRef, useEffect } from "react";
import { UploadCloud, Image as ImageIcon, Download, Settings2, Loader2, Key, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function StyleMatch() {
  const [step, setStep] = useState(1);
  const [settings, setSettings] = useState({ provider: "gemini", apiKey: "", ollamaUrl: "http://localhost:11434", ollamaModel: "gemma4:e4b" });
  
  useEffect(() => {
    // Load config on mount
    const prov = localStorage.getItem("ai_provider") || "gemini";
    const key = localStorage.getItem("gemini_key") || "";
    const ourl = localStorage.getItem("ollama_url") || "http://localhost:11434";
    const omodel = localStorage.getItem("ollama_model") || "gemma4:e4b";
    setSettings({ provider: prov, apiKey: key, ollamaUrl: ourl, ollamaModel: omodel });
  }, []);

  const [benchmarkImage, setBenchmarkImage] = useState(null);
  const [targetImage, setTargetImage] = useState(null);
  
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  
  const [filters, setFilters] = useState({
    brightness: 100, contrast: 100, saturation: 100, sepia: 0, hueRotate: 0
  });

  const canvasRef = useRef(null);

  const readImage = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleBenchmarkUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const dataUrl = await readImage(file);
    setBenchmarkImage(dataUrl);
    
    setIsAnalyzing(true);
    setAnalysisError("");
    
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          image: dataUrl,
          provider: settings.provider,
          apiKey: settings.apiKey,
          ollamaUrl: settings.ollamaUrl,
          ollamaModel: settings.ollamaModel
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to analyze image");
      }

      const data = await res.json();
      if (data.filters) setFilters(data.filters);
      setStep(2);
    } catch (err) {
      console.error(err);
      setAnalysisError(err.message || "Failed to analyze image style.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleTargetUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setTargetImage(await readImage(file));
    setStep(3);
  };

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas || !targetImage) return;

    const ctx = canvas.getContext("2d");
    const img = new window.Image();
    
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      const filterString = `brightness(${filters.brightness}%) contrast(${filters.contrast}%) saturate(${filters.saturation}%) sepia(${filters.sepia}%) hue-rotate(${filters.hueRotate}deg)`.trim();
      ctx.filter = filterString;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    };
    img.src = targetImage;
  };

  useEffect(() => {
    if (step === 3) drawCanvas();
  }, [filters, targetImage, step]);

  const handleDownload = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.toBlob(async (blob) => {
      try {
        if (window.showSaveFilePicker) {
          const handle = await window.showSaveFilePicker({
            suggestedName: 'styled-image.png',
            types: [{ description: 'PNG Image', accept: {'image/png': ['.png']} }],
          });
          const writable = await handle.createWritable();
          await writable.write(blob);
          await writable.close();
        } else {
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "styled-image.png";
          a.click();
          URL.revokeObjectURL(url);
        }
      } catch (err) {
        if (err.name !== 'AbortError') console.error("Save failed:", err);
      }
    }, 'image/png');
  };

  const handleFilterChange = (key, val) => setFilters(prev => ({ ...prev, [key]: parseInt(val, 10) }));

  return (
    <main className="container" style={{ padding: "4rem 2rem" }}>
      <div style={{ marginBottom: "2rem" }}>
        <Link href="/" className="btn btn-secondary" style={{ padding: "0.5rem 1rem" }}>
          <ArrowLeft size={16} /> Back to Dashboard
        </Link>
      </div>

      <div style={{ textAlign: "center", marginBottom: "3rem" }}>
        <h1>Style Matcher</h1>
        <p>Extract the aesthetic footprint of an image and apply it magically.</p>
        <span style={{ display: "inline-block", marginTop: "0.5rem", padding: "0.25rem 0.75rem", background: "rgba(255,255,255,0.1)", borderRadius: "100px", fontSize: "0.875rem" }}>
          Running on: <strong style={{ color: "var(--accent-hover)", textTransform: "capitalize" }}>{settings.provider}</strong>
        </span>
      </div>

      <div className="glass-panel" style={{ padding: "2rem", marginBottom: "2rem" }}>
        {step === 1 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
            <div>
              <h2 style={{ marginBottom: "1rem" }}>1. Upload Benchmark Image</h2>
              <p style={{ marginBottom: "1rem" }}>This image contains the color grading and mood you want to extract.</p>
              
              <label className="upload-zone">
                <UploadCloud className="upload-icon" />
                <span style={{ fontSize: "1.125rem", fontWeight: "500" }}>Click or Drag Benchmark Image Here</span>
                <input type="file" accept="image/*" style={{ display: "none" }} onChange={handleBenchmarkUpload} disabled={isAnalyzing} />
              </label>
            </div>

            {isAnalyzing && (
              <div style={{ display: "flex", alignItems: "center", gap: "1rem", color: "var(--accent-hover)", justifyContent: "center" }}>
                <Loader2 className="loader" /> Analyzing mood using {settings.provider}...
              </div>
            )}
            
            {analysisError && (
              <div style={{ padding: "1rem", background: "rgba(239, 68, 68, 0.2)", border: "1px solid rgba(239, 68, 68, 0.4)", borderRadius: "var(--border-radius-md)", color: "#fca5a5" }}>
                {analysisError}
              </div>
            )}
          </div>
        )}

        {step === 2 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2>2. Upload Target Image</h2>
              <button className="btn btn-secondary" onClick={() => setStep(1)}>Back</button>
            </div>
            
            <div className="sliders-grid" style={{ opacity: 0.7, pointerEvents: "none", background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "var(--border-radius-md)" }}>
               {Object.entries(filters).map(([key, value]) => (
                 <div key={key} className="slider-group">
                   <div className="slider-group-header">
                     <span className="label" style={{textTransform: "capitalize"}}>{key}</span>
                     <span className="slider-value">{value}</span>
                   </div>
                 </div>
               ))}
            </div>

            <label className="upload-zone">
              <ImageIcon className="upload-icon" />
              <span style={{ fontSize: "1.125rem", fontWeight: "500" }}>Upload Image to Style</span>
              <input type="file" accept="image/*" style={{ display: "none" }} onChange={handleTargetUpload} />
            </label>
          </div>
        )}

        {step === 3 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2>3. Fine-Tune & Export</h2>
              <button className="btn btn-secondary" onClick={() => setStep(2)}>Back to Target</button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "2rem", alignItems: "start" }}>
              <div style={{ overflow: "hidden", borderRadius: "12px", background: "rgba(0,0,0,0.4)" }}>
                <canvas ref={canvasRef} style={{ width: "100%", height: "auto", display: "block" }} />
              </div>
              
              <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Settings2 size={20} color="var(--accent-hover)" />
                  <h3 style={{ margin: 0, fontSize: "1.25rem" }}>Live Filters</h3>
                </div>
                
                <div className="sliders-grid" style={{ display: "flex", flexDirection: "column" }}>
                  {["brightness", "contrast", "saturation", "sepia"].map((key) => (
                    <div className="slider-group" key={key}>
                      <div className="slider-group-header">
                        <span className="label" style={{textTransform: "capitalize"}}>{key}</span>
                        <span className="slider-value">{filters[key]}%</span>
                      </div>
                      <input type="range" min="0" max="200" value={filters[key]} onChange={(e) => handleFilterChange(key, e.target.value)} className="range-slider" />
                    </div>
                  ))}
                  <div className="slider-group">
                    <div className="slider-group-header">
                      <span className="label">Hue Rotate</span>
                      <span className="slider-value">{filters.hueRotate}°</span>
                    </div>
                    <input type="range" min="-180" max="180" value={filters.hueRotate} onChange={(e) => handleFilterChange('hueRotate', e.target.value)} className="range-slider" />
                  </div>
                </div>

                <button className="btn btn-primary" onClick={handleDownload} style={{ width: "100%", marginTop: "1rem" }}>
                  <Download size={20} /> Save Image
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
