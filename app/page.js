"use client";

import { useState, useEffect } from "react";
import { ImageIcon, Sparkles, Scissors, Folder } from "lucide-react";

// Component Imports
import ToolCard from "../components/ToolCard";
import SettingsPanel from "../components/SettingsPanel";

export default function LandingPage() {
  const [provider, setProvider] = useState("gemini");
  const [geminiKey, setGeminiKey] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("http://192.168.1.222:11434");
  const [ollamaModel, setOllamaModel] = useState("gemma4:e4b");
  const [benchmarkFolder, setBenchmarkFolder] = useState("");

  useEffect(() => {
    setProvider(localStorage.getItem("ai_provider") || "gemini");
    setGeminiKey(localStorage.getItem("gemini_key") || "");
    setOllamaUrl(localStorage.getItem("ollama_url") || "http://192.168.1.222:11434");
    setOllamaModel(localStorage.getItem("ollama_model") || "gemma4:e4b");
    setBenchmarkFolder(localStorage.getItem("benchmark_folder") || "");
  }, []);

  const saveSettings = (k, v) => {
    localStorage.setItem(k, v);
  };

  return (
    <main className="container" style={{ padding: "4rem 2rem" }}>
      <header style={{ textAlign: "center", marginBottom: "4rem" }}>
        <h1 style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}>
          <Sparkles color="var(--accent-base)" size={40} />
          AI Image Workbench
        </h1>
        <p>Your local suite for intelligent image manipulation.</p>
      </header>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "2rem", marginBottom: "4rem" }}>
        <ToolCard 
          href="/style-match" 
          title="Style Matcher" 
          description="Extract color grading from a benchmark and apply it magically via AI." 
          icon={ImageIcon} 
        />
        
        <ToolCard 
          href="/remove-bg" 
          title="Background Removal" 
          description="Leverage high-precision local WASM models to instantly isolate objects. Completely private and ultra-fast." 
          icon={Scissors} 
        />

        <ToolCard 
          href="/batch-studio" 
          title="AI Batch Studio" 
          description="Massive backend parallel processing. Auto-cull out-of-focus RAWs and generate coaching reports." 
          icon={Folder} 
        />

        <ToolCard 
          href="/cull" 
          title="RLHF Workspace" 
          description="Swipe to cull. Train your local model's aesthetic intelligence in real-time." 
          icon={Sparkles} 
        />
      </section>

      <SettingsPanel 
        provider={provider}
        setProvider={setProvider}
        geminiKey={geminiKey}
        setGeminiKey={setGeminiKey}
        ollamaUrl={ollamaUrl}
        setOllamaUrl={setOllamaUrl}
        ollamaModel={ollamaModel}
        setOllamaModel={setOllamaModel}
        benchmarkFolder={benchmarkFolder}
        setBenchmarkFolder={setBenchmarkFolder}
        saveSettings={saveSettings}
      />
    </main>
  );
}
