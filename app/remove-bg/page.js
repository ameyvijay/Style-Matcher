"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { UploadCloud, Download, Loader2, ArrowLeft, CheckCircle, XCircle, Eraser, Brush, Save } from "lucide-react";

export default function RemoveBackground() {
  const [step, setStep] = useState(1);
  const [isProcessing, setIsProcessing] = useState(false);
  
  const [sourceFile, setSourceFile] = useState(null);
  const [resultUrl, setResultUrl] = useState(null);
  
  // Refinement State
  const [isRefining, setIsRefining] = useState(false);
  const [brushMode, setBrushMode] = useState("erase"); // "erase" | "restore"
  const [brushSize, setBrushSize] = useState(30);
  
  const [originalImageObj, setOriginalImageObj] = useState(null);
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  
  const isDrawing = useRef(false);
  const lastPos = useRef({ x: 0, y: 0 });
  
  // Accept source file and automatically trigger processing
  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSourceFile(file);
    
    // Create an Image object for the original image for restore mode
    const origUrl = URL.createObjectURL(file);
    const img = new window.Image();
    img.onload = () => setOriginalImageObj(img);
    img.src = origUrl;

    await processImage(file);
  };

  const processImage = async (file) => {
    setIsProcessing(true);
    setStep(2); 
    
    try {
      const { removeBackground } = await import("@imgly/background-removal");
      const imageBlob = await removeBackground(file);
      const url = URL.createObjectURL(imageBlob);
      setResultUrl(url);
    } catch (err) {
      console.error("Background removal failed:", err);
      alert("Failed to remove background. Please try a different image.");
      setStep(1);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRetry = () => {
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    setResultUrl(null);
    processImage(sourceFile); 
  };

  // Switch to Manual Refinement Studio
  const startRefinement = () => {
    setIsRefining(true);
  };

  // Mount canvas initially with the AI generated result
  useEffect(() => {
    if (isRefining && canvasRef.current && resultUrl) {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      
      const img = new window.Image();
      img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      };
      img.src = resultUrl;
    }
  }, [isRefining, resultUrl]);

  const getMousePos = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    // For touch devices or mouse
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

    return {
      x: (clientX - rect.left) * scaleX,
      y: (clientY - rect.top) * scaleY
    };
  };

  const handlePointerDown = (e) => {
    isDrawing.current = true;
    lastPos.current = getMousePos(e);
  };

  const handlePointerMove = (e) => {
    if (!isDrawing.current || !canvasRef.current) return;
    const currentPos = getMousePos(e);
    const ctx = canvasRef.current.getContext("2d");
    
    ctx.beginPath();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = brushSize;
    ctx.moveTo(lastPos.current.x, lastPos.current.y);
    ctx.lineTo(currentPos.x, currentPos.y);

    if (brushMode === "erase") {
      ctx.globalCompositeOperation = "destination-out";
      ctx.strokeStyle = "rgba(0,0,0,1)";
      ctx.stroke();
    } else {
      // Restore mode using canvas pattern magic
      if (originalImageObj) {
        ctx.globalCompositeOperation = "source-over";
        const pattern = ctx.createPattern(originalImageObj, "no-repeat");
        // Ensure pattern is aligned safely to top left
        // Note: CanvasPattern matrices can be set if needed, but defaults to 0,0 aligned to canvas!
        ctx.strokeStyle = pattern;
        ctx.stroke();
      }
    }
    
    // Reset back to default
    ctx.globalCompositeOperation = "source-over";
    lastPos.current = currentPos;
  };

  const handlePointerUp = () => {
    isDrawing.current = false;
  };

  const finishRefinement = () => {
    const canvas = canvasRef.current;
    if (canvas) {
       canvas.toBlob((blob) => {
         const newUrl = URL.createObjectURL(blob);
         if (resultUrl) URL.revokeObjectURL(resultUrl);
         setResultUrl(newUrl);
         setIsRefining(false);
       }, "image/png");
    } else {
       setIsRefining(false);
    }
  };

  const handleAccept = () => {
    setStep(3);
  };

  const downloadImage = (scale) => {
    if (!resultUrl) return;

    const img = new window.Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      
      canvas.toBlob(async (blob) => {
        try {
          if (window.showSaveFilePicker) {
            const handle = await window.showSaveFilePicker({
              suggestedName: `isolated-${scale*100}pct.png`,
              types: [{ description: 'PNG Image', accept: {'image/png': ['.png']} }],
            });
            const writable = await handle.createWritable();
            await writable.write(blob);
            await writable.close();
          } else {
            const downloadUrl = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `isolated-${scale*100}pct.png`;
            a.click();
            URL.revokeObjectURL(downloadUrl);
          }
        } catch (err) {
          if (err.name !== 'AbortError') console.error("Save failed:", err);
        }
      }, "image/png");
    };
    img.src = resultUrl;
  };

  return (
    <main className="container" style={{ padding: "4rem 2rem" }}>
      <div style={{ marginBottom: "2rem" }}>
        <Link href="/" className="btn btn-secondary" style={{ padding: "0.5rem 1rem" }}>
          <ArrowLeft size={16} /> Back to Dashboard
        </Link>
      </div>

      <div style={{ textAlign: "center", marginBottom: "3rem" }}>
        <h1>Background Removal</h1>
        <p>High-precision local object isolation with manual studio refinement perfectly processed offline.</p>
      </div>

      {isRefining ? (
        <div className="glass-panel" style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2>Manual Studio Refinement</h2>
            <button className="btn btn-primary" onClick={finishRefinement}>
              <Save size={18} /> Apply Changes
            </button>
          </div>
          
          {/* Toolbar */}
          <div style={{ display: "flex", gap: "2rem", alignItems: "center", flexWrap: "wrap", background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "12px" }}>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className={`btn ${brushMode === "erase" ? "btn-primary" : "btn-secondary"}`} onClick={() => setBrushMode("erase")}>
                <Eraser size={18} /> Erase
              </button>
              <button className={`btn ${brushMode === "restore" ? "btn-primary" : "btn-secondary"}`} onClick={() => setBrushMode("restore")}>
                <Brush size={18} /> Restore
              </button>
            </div>
            
            <div style={{ flex: 1, display: "flex", alignItems: "center", gap: "1rem" }}>
              <span className="label">Brush Size: {brushSize}px</span>
              <input 
                type="range" min="5" max="200" 
                value={brushSize} 
                onChange={(e) => setBrushSize(parseInt(e.target.value))}
                className="range-slider"
                style={{ maxWidth: "200px" }}
              />
            </div>
            
            <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
               Hint: Use the <strong>Restore</strong> brush to paint original pixels back if the AI cut off a piece of your object!
            </div>
          </div>

          <div style={{
            position: "relative",
            width: "100%",
            maxWidth: "800px",
            margin: "0 auto",
            border: "2px solid var(--accent-base)",
            borderRadius: "12px",
            overflow: "hidden",
            cursor: `crosshair`
          }}>
             {/* The faint original image as a guide layer perfectly aligned below */}
             {originalImageObj && (
                 // eslint-disable-next-line @next/next/no-img-element
                 <img src={originalImageObj.src} style={{ 
                     position: "absolute", 
                     top: 0, left: 0, 
                     width: "100%", height: "100%", 
                     objectFit: "contain", 
                     opacity: 0.3,
                     pointerEvents: "none" 
                 }} alt="Original Guide Layer" />
             )}

             <canvas 
                ref={canvasRef}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerOut={handlePointerUp}
                style={{ 
                  display: "block",
                  width: "100%", 
                  height: "auto", 
                  objectFit: "contain",
                  background: `
                    linear-gradient(45deg, rgba(31,31,31,0.5) 25%, transparent 25%, transparent 75%, rgba(31,31,31,0.5) 75%, rgba(31,31,31,0.5)), 
                    linear-gradient(45deg, rgba(31,31,31,0.5) 25%, transparent 25%, transparent 75%, rgba(31,31,31,0.5) 75%, rgba(31,31,31,0.5))
                  `,
                  backgroundSize: "20px 20px",
                  backgroundPosition: "0 0, 10px 10px",
                  backgroundColor: "rgba(44,44,44,0.5)",
                }} 
             />
          </div>
        </div>
      ) : (
        <div className="glass-panel" style={{ padding: "2rem", marginBottom: "2rem" }}>
          
          {step === 1 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
              <h2 style={{ marginBottom: "1rem" }}>Upload Image</h2>
              <label className="upload-zone">
                <UploadCloud className="upload-icon" />
                <span style={{ fontSize: "1.125rem", fontWeight: "500" }}>Upload Image to Isolate</span>
                <input type="file" accept="image/*" style={{ display: "none" }} onChange={handleUpload} />
              </label>
            </div>
          )}

          {step === 2 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem", alignItems: "center" }}>
              <h2>AI Processing & Inspection</h2>
              
              <div style={{
                width: "100%",
                maxWidth: "600px",
                minHeight: "300px",
                background: `
                  linear-gradient(45deg, #1f1f1f 25%, transparent 25%, transparent 75%, #1f1f1f 75%, #1f1f1f), 
                  linear-gradient(45deg, #1f1f1f 25%, transparent 25%, transparent 75%, #1f1f1f 75%, #1f1f1f)
                `,
                backgroundSize: "20px 20px",
                backgroundPosition: "0 0, 10px 10px",
                backgroundColor: "#2c2c2c",
                border: "1px solid var(--glass-border)",
                borderRadius: "12px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                overflow: "hidden"
              }}>
                {isProcessing ? (
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem", color: "var(--accent-hover)" }}>
                    <Loader2 className="loader" size={32} />
                    <span>Isolating pixels (running local model)...</span>
                  </div>
                ) : resultUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={resultUrl} alt="Isolated Result" style={{ width: "100%", height: "auto", objectFit: "contain" }} />
                ) : null}
              </div>

              {!isProcessing && resultUrl && (
                <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "1.5rem", marginTop: "1rem", width: "100%" }}>
                  <button className="btn btn-secondary" onClick={handleRetry}>
                    <XCircle size={18} /> Re-run AI Extractor
                  </button>
                  <button className="btn btn-secondary" style={{ borderColor: "var(--accent-base)" }} onClick={startRefinement}>
                    <Brush size={18} color="var(--accent-hover)" /> Manually Refine Mask
                  </button>
                  <button className="btn btn-primary" onClick={handleAccept}>
                    <CheckCircle size={18} /> Accept Result
                  </button>
                </div>
              )}
            </div>
          )}

          {step === 3 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem", alignItems: "center" }}>
              <h2>Export Image</h2>
              <p>Select the resolution format. You will be prompted to rename and choose your download folder.</p>
              
              <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", justifyContent: "center" }}>
                <button className="btn btn-secondary" onClick={() => downloadImage(0.5)}>
                  <Download size={18} /> Low Resolution (50%)
                </button>
                <button className="btn btn-primary" onClick={() => downloadImage(0.75)}>
                  <Download size={18} /> Medium Resolution (75%)
                </button>
                <button className="btn btn-primary" onClick={() => downloadImage(1.0)}>
                  <Download size={18} /> High Resolution (Native)
                </button>
              </div>
              
              <button className="btn btn-secondary" onClick={() => {
                setStep(1);
                setResultUrl(null);
                setSourceFile(null);
              }} style={{ marginTop: "2rem" }}>
                Start Over
              </button>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
