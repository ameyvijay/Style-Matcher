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
        
        <InputGroup label="Global Benchmark Directory" icon={Folder} description="Universal aesthetic baseline for Style Matching and Batch Processing.">
          <input 
            type="text"
            className="input" 
            placeholder="/Users/Amey/Desktop/MyBestPhotos" 
            value={benchmarkFolder}
            onChange={(e) => {
              setBenchmarkFolder(e.target.value);
              saveSettings('benchmark_folder', e.target.value);
            }}
          />
        </InputGroup>
      </div>
    </div>
  );
}
