"use client";

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
  benchmarkFolder,
  setBenchmarkFolder,
  saveSettings 
}) {
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
             <input 
               type="text"
               className="input" 
               placeholder="e.g. llava, gemma4:e4b" 
               value={ollamaModel}
               onChange={(e) => {
                 setOllamaModel(e.target.value);
                 saveSettings('ollama_model', e.target.value);
               }}
             />
           </InputGroup>
           </>
        )}

        <hr style={{ margin: "1rem 0", borderColor: "var(--glass-border)" }} />
        
        <InputGroup label="Global Benchmark Directory" icon={Folder} description="Universal aesthetic baseline for Style Matching and Batch Processing. Drag a folder here to auto-fill.">
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input 
              type="text"
              className="input" 
              placeholder="/Users/shivamagent/Desktop/MyBestPhotos" 
              value={benchmarkFolder}
              onChange={(e) => {
                setBenchmarkFolder(e.target.value);
                saveSettings('benchmark_folder', e.target.value);
              }}
              onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--accent-hover)'; }}
              onDragLeave={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--glass-border)'; }}
              onDrop={(e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = 'var(--glass-border)';
                // MacOS Drag-and-Drop to text input is native, 
                // but we add this handler just to ensure it captures if the OS doesn't paste automatically.
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
                  const res = await fetch("http://192.168.1.222:8000/api/pick-folder");
                  if (!res.ok) {
                    const errData = await res.json();
                    console.log("Folder picker:", errData.detail);
                    return;
                  }
                  const data = await res.json();
                  setBenchmarkFolder(data.path);
                  saveSettings('benchmark_folder', data.path);
                } catch (err) {
                  console.error("Folder picker failed:", err);
                }
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
