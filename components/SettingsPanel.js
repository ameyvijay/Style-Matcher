"use client";

import { useState, useEffect } from "react";
import { Settings, Key, Server, Folder } from "lucide-react";
import InputGroup from "./InputGroup";

export default function SettingsPanel({ 
  provider, 
  setProvider, 
  geminiKey, 
  setGeminiKey,
  ollamaUrl,
  setOllamaUrl,
  ollamaModel,
  setOllamaModel,
  saveSettings 
}) {
  const [availableModels, setAvailableModels] = useState(["moondream:latest"]);
  const [sourceRoot, setSourceRoot] = useState("");

  useEffect(() => {
    async function fetchConfig() {
      try {
        const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
        const res = await fetch(`${baseUrl}/api/config/source-root`);
        if (res.ok) {
          const data = await res.json();
          setSourceRoot(data.source_root || "");
        }
      } catch (e) {}
    }
    fetchConfig();
  }, []);

  const updateSourceRoot = async (path) => {
    setSourceRoot(path || "");
    try {
      const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
      const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
      await fetch(`${baseUrl}/api/config/source-root`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_root: path })
      });
    } catch (e) {}
  };

  useEffect(() => {
    let controller = new AbortController();
    async function fetchModels() {
      try {
        const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
        const res = await fetch(`${baseUrl}/api/ollama-tags`, { signal: controller.signal });
        if (!res.ok) return;
        
        const data = await res.json();
        if (data.success && data.models && data.models.length > 0) {
          setAvailableModels(data.models);
          // Auto-migrate to actual first model if current isn't valid
          if (!data.models.includes(ollamaModel)) {
            const firstModel = data.models[0] || "moondream:latest";
            setOllamaModel(firstModel);
            saveSettings('ollama_model', firstModel);
          }
        }
      } catch (e) {
        if (e.name === 'AbortError') return;
        console.warn("Ollama unavailable - using default list");
      }
    }
    if (provider === "ollama") fetchModels();
    return () => controller.abort();
  }, [provider, ollamaModel, setOllamaModel, saveSettings]);
  return (
    <div className="glass-panel" style={{ padding: "2rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <Settings size={20} color="var(--accent-hover)" />
        <h2 style={{ margin: 0 }}>Global AI Settings</h2>
      </div>
      
      <p style={{ marginBottom: "2rem" }}>Configure the model provider used by the workbench tools.</p>

      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="input-group">
          <span className="label">AI Provider</span>
          <div style={{ display: "flex", gap: "1rem" }}>
            <button 
              className={`btn ${provider === 'gemini' ? 'btn-primary' : 'btn-secondary'}`} 
              onClick={() => { setProvider('gemini'); saveSettings('ai_provider', 'gemini'); }}
            >
              Gemini (Cloud)
            </button>
            <button 
              className={`btn ${provider === 'ollama' ? 'btn-primary' : 'btn-secondary'}`} 
              onClick={() => { setProvider('ollama'); saveSettings('ai_provider', 'ollama'); }}
            >
              Ollama (Local)
            </button>
          </div>
        </div>

        {provider === "gemini" && (
           <InputGroup label="Gemini API Key" icon={Key} description="Leave empty if set via .env.local GEMINI_API_KEY">
             <input 
               type="password"
               className="input" 
               placeholder="AIzaSy..." 
               value={geminiKey}
               onChange={(e) => {
                 setGeminiKey(e.target.value);
                 saveSettings('gemini_key', e.target.value);
               }}
             />
           </InputGroup>
        )}

        {provider === "ollama" && (
           <>
           <InputGroup label="Ollama Default Model URL" icon={Server} description="Make sure Ollama is running and OLLAMA_ORIGINS is configured.">
             <input 
               type="text"
               className="input" 
               placeholder="http://localhost:11434" 
               value={ollamaUrl}
               onChange={(e) => {
                 setOllamaUrl(e.target.value);
                 saveSettings('ollama_url', e.target.value);
               }}
             />
           </InputGroup>

           <InputGroup label="Ollama Model Name" icon={Server} description="Ensure the executed model supports multimodal inputs.">
             <select 
               className="input" 
               value={ollamaModel}
               onChange={(e) => {
                 setOllamaModel(e.target.value);
                 saveSettings('ollama_model', e.target.value);
               }}
               style={{ appearance: "auto" }}
             >
               {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
             </select>
           </InputGroup>
           </>
        )}

        <hr style={{ margin: "1rem 0", borderColor: "var(--glass-border)" }} />
        
        <InputGroup label="Source Library Root (Local/NAS)" icon={Folder} description="The top-level folder monitored by the background daemon. Drag your main photo library folder here.">
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input 
              type="text"
              className="input" 
              placeholder="/Users/shivamagent/Pictures/MyLibrary" 
              value={sourceRoot}
              onChange={(e) => updateSourceRoot(e.target.value)}
              onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--accent-hover)'; }}
              onDragLeave={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--glass-border)'; }}
              onDrop={(e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = 'var(--glass-border)';
              }}
              style={{ flex: 1 }}
            />
            <button 
              type="button"
              className="btn btn-secondary"
              style={{ padding: "0 1rem" }}
              title="Browse Folder"
              onClick={async () => {
                try {
                  const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
                  const res = await fetch(`${baseUrl}/api/pick-folder`);
                  if (res.ok) {
                    const data = await res.json();
                    updateSourceRoot(data.path);
                  }
                } catch (err) {}
              }}
            >
              <Folder size={18} />
            </button>
          </div>
        </InputGroup>
      </div>
    </div>
  );
}
