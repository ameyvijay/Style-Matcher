"use client";

import { useState, useEffect } from "react";
import { Settings, Database, BrainCircuit, Activity } from "lucide-react";

// Component Imports
import SettingsPanel from "../../components/SettingsPanel";

// ── Tab Definitions ────────────────────────────────────────────────────────────
const TABS = [
  { id: "ai-settings",     label: "AI Settings",      Icon: Settings      },
  { id: "data-governance", label: "Data Governance",  Icon: Database      },
  { id: "model-ops",       label: "Model Ops",        Icon: BrainCircuit  },
  { id: "telemetry",       label: "Telemetry",        Icon: Activity      },
];

// ── Shell Panel Component ──────────────────────────────────────────────────────
// Reusable placeholder for tabs that are not yet wired to a backend endpoint.
function ShellPanel({ title, description, placeholders }) {
  return (
    <div style={styles.shellPanel}>
      <div style={styles.shellHeader}>
        <h2 style={styles.shellTitle}>{title}</h2>
        <p style={styles.shellDescription}>{description}</p>
      </div>
      <div style={styles.shellGrid}>
        {placeholders.map((item, i) => (
          <div key={i} style={styles.shellCard}>
            <div style={styles.shellCardHeader}>
              <item.Icon size={16} color={item.color || "var(--accent-base)"} />
              <span style={styles.shellCardTitle}>{item.title}</span>
              <span style={{ ...styles.shellBadge, borderColor: item.color || "rgba(96,165,250,0.4)", color: item.color || "#60a5fa" }}>
                {item.status}
              </span>
            </div>
            <p style={styles.shellCardBody}>{item.body}</p>
            {/* TODO: Wire endpoint → {item.endpoint} */}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Data Governance Tab ────────────────────────────────────────────────────────
function DataGovernanceTab() {
  const { Database: Db, Tag, Clock, RotateCcw } = require("lucide-react");
  const [stats, setStats] = useState({ golden: "—", training: "—", eval: "—", total_annotations: 0 });

  useEffect(() => {
    async function fetchStats() {
      try {
        const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
        const res = await fetch(`${baseUrl}/api/admin/dataset-stats`);
        const data = await res.json();
        setStats(data);
      } catch (e) {
        console.error("Failed to fetch dataset stats:", e);
      }
    }
    fetchStats();
  }, []);

  const datasetStrata = [
    {
      label: "Golden Set",
      count: stats.golden,
      description: "High-confidence accepted images used as positive exemplars for RAG retrieval.",
      color: "#f59e0b",
      border: "rgba(245,158,11,0.3)",
      bg: "rgba(245,158,11,0.06)",
    },
    {
      label: "Training Split",
      count: stats.training,
      description: "70% of annotated pairs streamed into the LoRA fine-tune queue.",
      color: "#10b981",
      border: "rgba(16,185,129,0.3)",
      bg: "rgba(16,185,129,0.06)",
    },
    {
      label: "Eval Split",
      count: stats.eval,
      description: "Held-out 30% used for staging eval benchmarks before model promotion.",
      color: "#60a5fa",
      border: "rgba(96,165,250,0.3)",
      bg: "rgba(96,165,250,0.06)",
    },
  ];

  return (
    <div style={styles.shellPanel}>
      <div style={styles.shellHeader}>
        <h2 style={styles.shellTitle}>Data Governance</h2>
        <p style={styles.shellDescription}>
          Inspect stratified dataset splits, manage TTL annotations, and trigger decision reversals.
        </p>
      </div>

      {/* Dataset Strata Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
        {datasetStrata.map((stratum) => (
          <div key={stratum.label} style={{ ...styles.dataCard, background: stratum.bg, border: `1px solid ${stratum.border}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
              <span style={{ fontSize: "0.65rem", textTransform: "uppercase", letterSpacing: "0.12em", color: stratum.color, fontWeight: "700" }}>
                {stratum.label}
              </span>
              <span style={{ fontSize: "1.8rem", fontWeight: "800", color: stratum.color, fontFamily: "'Courier New', monospace", lineHeight: 1 }}>
                {stratum.count}
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.45)", lineHeight: "1.55", margin: 0 }}>
              {stratum.description}
            </p>
          </div>
        ))}
      </div>

      {/* Data Integrity Ops */}
      <div style={styles.actionRail}>
        <div style={styles.actionRailHeader}>
          <div style={{ ...styles.opIconWrap, background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.2)" }}>
            <RotateCcw size={16} color="#f87171" />
          </div>
          <span style={styles.actionRailLabel}>Data Integrity Ops</span>
          <span style={styles.wiredBadge}>Endpoint Wired</span>
        </div>

        <div style={{ display: "flex", gap: "1rem" }}>
          <button 
            style={{ ...styles.actionBtn, opacity: 1, cursor: "pointer", borderColor: "rgba(248,113,113,0.3)", color: "#f87171" }}
            onClick={async () => {
              if (!confirm("Are you sure you want to purge annotations older than 10 days?")) return;
              try {
        const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
                const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
                const res = await fetch(`${baseUrl}/api/annotations/ttl-cleanup`, { method: "POST" });
                const data = await res.json();
                alert(`Purge Complete: Deleted ${data.deleted_count} stale annotations.`);
              } catch (e) {
                alert("Purge Failed: Check backend logs.");
              }
            }}
          >
            <Clock size={14} />
            TTL Purge (10d)
          </button>

          <button 
            style={{ ...styles.actionBtn, opacity: 1, cursor: "pointer", borderColor: "rgba(96,165,250,0.3)", color: "#60a5fa" }}
            onClick={() => {
              const hash = prompt("Enter Photo Hash for Reversal:");
              if (!hash) return;
              // Trigger reversal
              (async () => {
                 try {
                   const hostname = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`;
                   const res = await fetch(`${baseUrl}/api/annotations/reverse`, {
                     method: "POST",
                     headers: { "Content-Type": "application/json" },
                     body: JSON.stringify({ photo_hash: hash })
                   });
                   const data = await res.json();
                   alert(`Reversed: ${data.from} → ${data.to}`);
                 } catch (e) {
                   alert("Reversal Failed.");
                 }
              })();
            }}
          >
            <RotateCcw size={14} />
            Decision Reversal
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Model Ops Tab ─────────────────────────────────────────────────────────────
function ModelOpsTab() {
  const { Zap, RefreshCw, FlaskConical, ChevronRight, Play, CheckCircle, Clock, Save, Plus, Sparkles, AlertCircle, Info, Trash2, AlertTriangle } = require("lucide-react");
  const [prompts, setPrompts] = useState([]);
  const [activePrompt, setActivePrompt] = useState(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [newPrompt, setNewPrompt] = useState({ version: "", system: "", user: "", notes: "" });
  const [isCreating, setIsCreating] = useState(false);
  const [recommendations, setRecommendations] = useState([]);

  const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
  const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();

  useEffect(() => {
    fetchPrompts();
    fetchRecommendations();
  }, []);

  const fetchPrompts = async () => {
    try {
      const res = await fetch(`${baseUrl}/api/prompts`);
      const data = await res.json();
      const promptsArray = Array.isArray(data) ? data : [];
      setPrompts(promptsArray);
      const active = promptsArray.find(p => p.is_production);
      if (active) setActivePrompt(active);
    } catch (e) { console.error(e); setPrompts([]); }
  };

  const fetchRecommendations = async () => {
    try {
      const res = await fetch(`${baseUrl}/api/admin/recommendations`);
      const data = await res.json();
      setRecommendations(data);
    } catch (e) { console.error(e); }
  };

  const handleTest = async (version) => {
    setIsTesting(true);
    setTestResults(null);
    try {
      const res = await fetch(`${baseUrl}/api/model/test-prompt?version=${version}`, { method: "POST" });
      const data = await res.json();
      if (data.error) alert(data.error);
      else {
        setTestResults(data);
        fetchPrompts(); // Refresh metrics
      }
    } catch (e) { alert("Test Failed"); }
    finally { setIsTesting(false); }
  };

  const handlePromote = async (version) => {
    if (!confirm(`Promote ${version} to Production? This will retire the current prompt.`)) return;
    try {
      await fetch(`${baseUrl}/api/prompts/${version}/promote`, { method: "POST" });
      fetchPrompts();
    } catch (e) { alert("Promotion Failed"); }
  };

  const handleCreate = async () => {
    try {
      const res = await fetch(`${baseUrl}/api/prompts/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version: newPrompt.version,
          system_prompt: newPrompt.system,
          user_prompt: newPrompt.user,
          notes: newPrompt.notes
        })
      });
      if (res.ok) {
        setIsCreating(false);
        setNewPrompt({ version: "", system: "", user: "", notes: "" });
        fetchPrompts();
      }
    } catch (e) { alert("Creation Failed"); }
  };

  const handleOp = async (op) => {
    if (op.onTrigger) {
      await op.onTrigger();
      return;
    }
    // Generic POST handler
    try {
      const res = await fetch(`${baseUrl}${op.endpoint.replace("POST ", "")}`, { method: "POST" });
      if (res.ok) alert(`${op.title} Started Successfully`);
    } catch (e) { alert(`${op.title} Failed`); }
  };

  const ops = [
    {
      Icon: RefreshCw,
      title: "LoRA Fine-Tune",
      status: "Idle",
      color: "#10b981",
      body: "Trigger incremental LoRA weight updates from the latest accepted/rejected annotation batch.",
      endpoint: "POST /api/model/lora-update",
    },
    {
      Icon: Zap,
      title: "RAG Index Rebuild",
      status: "Idle",
      color: "#a78bfa",
      body: "Re-index all accepted exemplars into ChromaDB and refresh the semantic search vectors.",
      endpoint: "POST /api/admin/promote-golden-set",
      onTrigger: async () => {
        try {
          const res = await fetch(`${baseUrl}/api/admin/promotable-snapshots`);
          const data = await res.json();
          const snaps = Array.isArray(data) ? data : [];
          if (snaps.length === 0) {
            alert("No Golden Set snapshots found. Create one first in Data Governance.");
            return;
          }
          const version = prompt("Enter Snapshot Version to promote:\n\nAvailable:\n" + snaps.map(s => s.version).join("\n"));
          if (!version) return;
          
          const promoteRes = await fetch(`${baseUrl}/api/admin/promote-golden-set?snapshot_version=${version}`, { method: "POST" });
          const resData = await promoteRes.json();
          alert(`Promoted ${resData.promoted} vectors to RAG collection.`);
        } catch (e) { alert("RAG Rebuild Failed"); }
      }
    },
    {
      Icon: FlaskConical,
      title: "Staging Evaluation",
      status: "Not Run",
      color: "#f59e0b",
      body: "Run the held-out eval split through the current model and report accuracy + confusion matrix.",
      endpoint: "POST /api/model/compare",
      onTrigger: async () => {
        const tag = prompt("Enter Candidate Model Tag (Ollama):\ne.g., moondream:v2, llava:7b");
        if (!tag) return;
        try {
          const res = await fetch(`${baseUrl}/api/admin/promotable-snapshots`);
          const data = await res.json();
          const snaps = Array.isArray(data) ? data : [];
          if (snaps.length === 0) {
            alert("No Golden Set snapshots found. Create one first in Data Governance.");
            return;
          }
          const version = prompt("Enter Snapshot Version for Evaluation:\n" + snaps.map(s => s.version).join("\n"));
          if (!version) return;
          
          setIsTesting(true);
          const evalRes = await fetch(`${baseUrl}/api/model/compare?candidate_tag=${tag}&snapshot_version=${version}`, { method: "POST" });
          const evalData = await evalRes.json();
          setTestResults({
            version: `${tag} (Candidate)`,
            accuracy: evalData.candidate.accuracy,
            avg_latency: evalData.candidate.resources.p50_latency_ms,
            total_tested: evalData.candidate.resources.images_evaluated,
            verdict: evalData.verdict
          });
        } catch (e) { alert("Evaluation Failed"); }
        finally { setIsTesting(false); }
      }
    },
  ];

  const handleFlush = async () => {
    if (!confirm("⚠️ DANGER: This will surgically wipe all TEST inferences and skipped annotations. Proceed?")) return;
    try {
      const res = await fetch(`${baseUrl}/api/admin/flush-test-data`, { method: "POST" });
      const data = await res.json();
      alert(`Flush Complete: ${data.details.inferences_flushed} inferences, ${data.details.skips_cleared} skips cleared.`);
    } catch (e) { alert("Flush Failed"); }
  };

  return (
    <div style={styles.shellPanel}>
      <div style={styles.shellHeader}>
        <h2 style={styles.shellTitle}>Model Ops</h2>
        <p style={styles.shellDescription}>
          Trigger LoRA/RAG updates, inspect the AI Recommendation Engine state, and run Staging Evals.
        </p>
      </div>

      {/* ── AI Recommendation Engine ── */}
      {recommendations.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "2rem" }}>
          {recommendations.map((rec) => {
            const isHigh = rec.priority === "HIGH";
            const themeColor = isHigh ? "#f59e0b" : "#60a5fa";
            return (
              <div key={rec.id} style={{ ...styles.recBanner, borderColor: `${themeColor}40`, background: `${themeColor}08` }}>
                <div style={{ ...styles.opIconWrap, width: "32px", height: "32px", background: `${themeColor}20` }}>
                  {isHigh ? <Sparkles size={16} color={themeColor} /> : <Info size={16} color={themeColor} />}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: "800", color: "#fff" }}>{rec.title}</span>
                    <span style={{ ...styles.shellBadge, fontSize: "0.5rem", padding: "1px 5px", background: themeColor, color: "#000", border: "none" }}>
                      {rec.priority}
                    </span>
                  </div>
                  <p style={{ fontSize: "0.72rem", color: "rgba(255,255,255,0.5)", margin: "2px 0 0" }}>{rec.body}</p>
                </div>
                <button 
                  onClick={() => {
                    if (rec.id === "rag_rebuild") handleOp(ops[1]);
                    else if (rec.id === "prompt_opt") setActiveTab("model-ops");
                    else if (rec.id === "more_data") window.location.href = "/cull";
                  }}
                  style={{ ...styles.actionBtn, opacity: 1, cursor: "pointer", borderColor: themeColor, color: themeColor, fontSize: "0.65rem", padding: "0.4rem 0.8rem" }}
                >
                  {rec.action}
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginBottom: "3rem" }}>
        {ops.map((op) => (
          <div key={op.title} style={{ ...styles.opRow, borderColor: `${op.color}22` }}>
            <div style={{ ...styles.opIconWrap, background: `${op.color}18`, border: `1px solid ${op.color}40` }}>
              <op.Icon size={18} color={op.color} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "4px" }}>
                <span style={{ fontSize: "0.9rem", fontWeight: "700", color: "#fff" }}>{op.title}</span>
                <span style={{ ...styles.shellBadge, borderColor: `${op.color}55`, color: op.color }}>{op.status}</span>
              </div>
              <p style={{ fontSize: "0.76rem", color: "rgba(255,255,255,0.42)", margin: 0, lineHeight: "1.5" }}>{op.body}</p>
            </div>
            <button 
              onClick={() => handleOp(op)}
              style={{ ...styles.opTriggerBtn, borderColor: `${op.color}44`, color: op.color, opacity: 1, cursor: "pointer" }}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        ))}
      </div>

      {/* ── Prompt Playground ── */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "2rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
          <div>
            <h3 style={{ ...styles.shellTitle, fontSize: "1.1rem", marginBottom: "0.25rem" }}>Prompt Playground</h3>
            <p style={styles.shellDescription}>Version and test VLM instructions against the Golden Set.</p>
          </div>
          <button 
            onClick={() => setIsCreating(!isCreating)}
            style={{ ...styles.actionBtn, background: "var(--accent-base)", color: "#000", border: "none", padding: "0.5rem 1rem" }}
          >
            <Plus size={14} /> New Prompt
          </button>
        </div>

        {isCreating && (
          <div style={{ ...styles.opRow, flexDirection: "column", alignItems: "stretch", gap: "1rem", marginBottom: "2rem", background: "rgba(255,255,255,0.02)" }}>
            <input 
              placeholder="Version (e.g., v1.1-beta)" 
              value={newPrompt.version}
              onChange={e => setNewPrompt({...newPrompt, version: e.target.value})}
              style={styles.playgroundInput}
            />
            <textarea 
              placeholder="System Prompt (Persona & Rules)" 
              value={newPrompt.system}
              onChange={e => setNewPrompt({...newPrompt, system: e.target.value})}
              style={{ ...styles.playgroundInput, minHeight: "80px" }}
            />
            <textarea 
              placeholder="User Prompt Template ({placeholders})" 
              value={newPrompt.user}
              onChange={e => setNewPrompt({...newPrompt, user: e.target.value})}
              style={{ ...styles.playgroundInput, minHeight: "120px" }}
            />
            <div style={{ display: "flex", gap: "1rem", justifyContent: "flex-end" }}>
              <button onClick={() => setIsCreating(false)} style={styles.actionBtn}>Cancel</button>
              <button onClick={handleCreate} style={{ ...styles.actionBtn, borderColor: "var(--accent-base)", color: "var(--accent-base)" }}>
                <Save size={14} /> Save Draft
              </button>
            </div>
          </div>
        )}

        {isTesting && (
          <div style={{ padding: "2rem", textAlign: "center", background: "rgba(96,165,250,0.05)", borderRadius: "12px", border: "1px dashed #60a5fa", marginBottom: "1.5rem" }}>
            <RefreshCw className="animate-spin" size={24} color="#60a5fa" style={{ marginBottom: "1rem" }} />
            <div style={{ color: "#60a5fa", fontWeight: "600" }}>Running Golden Set Evaluation...</div>
            <div style={{ fontSize: "0.75rem", color: "rgba(96,165,250,0.6)", marginTop: "0.5rem" }}>M4 Memory Guard Active · Serializing Inferences</div>
          </div>
        )}

        {testResults && (
          <div style={{ padding: "1.5rem", background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.3)", borderRadius: "12px", marginBottom: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
              <CheckCircle size={20} color="#10b981" />
              <span style={{ fontWeight: "700", color: "#fff" }}>Test Complete: {testResults.version}</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
              <div style={styles.miniMetric}>
                <span style={styles.miniLabel}>Accuracy</span>
                <span style={styles.miniValue}>{(testResults.accuracy * 100).toFixed(1)}%</span>
              </div>
              <div style={styles.miniMetric}>
                <span style={styles.miniLabel}>Avg Latency</span>
                <span style={styles.miniValue}>{Math.round(testResults.avg_latency)}ms</span>
              </div>
              <div style={styles.miniMetric}>
                <span style={styles.miniLabel}>Samples</span>
                <span style={styles.miniValue}>{testResults.total_tested}</span>
              </div>
            </div>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {(prompts || []).map((p) => (
            <div key={p.version} style={{ ...styles.promptCard, borderLeft: p.is_production ? "4px solid #10b981" : "4px solid rgba(255,255,255,0.1)" }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
                  <span style={{ fontWeight: "800", color: "#fff" }}>{p.version}</span>
                  <span style={{ ...styles.shellBadge, borderColor: p.is_production ? "#10b981" : "rgba(255,255,255,0.2)", color: p.is_production ? "#10b981" : "rgba(255,255,255,0.4)" }}>
                    {p.status}
                  </span>
                  {p.golden_success_rate && (
                    <span style={{ fontSize: "0.7rem", color: "#60a5fa", fontWeight: "600" }}>
                      GS: {(p.golden_success_rate * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
                <p style={{ fontSize: "0.7rem", color: "rgba(255,255,255,0.3)", margin: 0, fontStyle: "italic" }}>
                  Created {new Date(p.created_at).toLocaleDateString()} · {p.total_inferences} inferences
                </p>
              </div>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button onClick={() => handleTest(p.version)} style={styles.iconBtn} title="Run Golden Test">
                  <Play size={14} />
                </button>
                {!p.is_production && (
                  <button onClick={() => handlePromote(p.version)} style={styles.iconBtn} title="Promote to Production">
                    <CheckCircle size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* ── Dangerous Ops ── */}
        <div style={{ marginTop: "3rem", padding: "1.5rem", background: "rgba(248,113,113,0.04)", border: "1px solid rgba(248,113,113,0.15)", borderRadius: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
            <AlertTriangle size={18} color="#f87171" />
            <span style={{ fontSize: "0.9rem", fontWeight: "700", color: "#f87171", textTransform: "uppercase", letterSpacing: "0.05em" }}>Dangerous Ops</span>
          </div>
          <p style={{ fontSize: "0.75rem", color: "rgba(248,113,113,0.6)", marginBottom: "1.5rem" }}>
            Surgically reset the system by clearing experimental test data. This action is irreversible.
          </p>
          <button 
            onClick={handleFlush}
            style={{ ...styles.actionBtn, opacity: 1, cursor: "pointer", borderColor: "rgba(248,113,113,0.4)", color: "#f87171", background: "rgba(248,113,113,0.06)" }}
          >
            <Trash2 size={14} />
            Flush Test Inferences & Skips
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Telemetry Tab ─────────────────────────────────────────────────────────────
function TelemetryTab() {
  const { Eye, Sparkles, ScanLine, MessageSquare, Cpu, HardDrive, Thermometer, Database } = require("lucide-react");
  const [telemetry, setTelemetry] = useState({ system: {}, models: {} });
  const [vitals, setVitals] = useState(null);

  useEffect(() => {
    let isActive = true;
    async function fetchData() {
      try {
        const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
        // Increase timeout for vitals during heavy RAW processing
        const [telRes, vitRes] = await Promise.all([
          fetch(`${baseUrl}/api/admin/telemetry`),
          fetch(`${baseUrl}/api/admin/vitals`)
        ]);
        
        if (!isActive) return;
        
        if (telRes.ok) {
          const telData = await telRes.json();
          setTelemetry(telData);
        }
        if (vitRes.ok) {
          const vitData = await vitRes.json();
          setVitals(vitData);
        }
      } catch (e) {
        console.warn("Telemetry poll delayed - backend processing heavy load");
      }
    }
    fetchData();
    const interval = setInterval(fetchData, 3000); // 3s for more real-time feel
    return () => {
      isActive = false;
      clearInterval(interval);
    };
  }, []);

  const models = [
    {
      Icon: ScanLine,
      name: "Laplacian Sharpness",
      key: "laplacian_v2", // Updated to match DB
      color: "#60a5fa",
      description: "OpenCV Laplacian variance — measures image focus and motion blur.",
    },
    {
      Icon: Eye,
      name: "NIMA Aesthetic",
      key: "nima_v1",
      color: "#a78bfa",
      description: "Neural Image Assessment model scoring technical & aesthetic quality.",
    },
    {
      Icon: Sparkles,
      name: "CLIP Embedding",
      key: "clip_vit_b32",
      color: "#10b981",
      description: "OpenCLIP ViT-B/32 — generates 512-dim image embeddings for RAG retrieval.",
    },
    {
      Icon: MessageSquare,
      name: "LLM Aesthetics (VLM)",
      key: "ollama_vlm",
      color: "#f59e0b",
      description: "Ollama-hosted VLM providing natural language coaching and tier classification.",
    },
  ];

  const modelMetrics = telemetry.models || {};

  return (
    <div style={styles.shellPanel}>
      <div style={styles.shellHeader}>
        <h2 style={styles.shellTitle}>Telemetry</h2>
        <p style={styles.shellDescription}>
          Real-time M4 hardware metrics and model inference health.
        </p>
      </div>

      {/* Hardware Metrics Strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
        <div style={styles.hwCard}>
          <Cpu size={14} color="var(--accent-base)" />
          <span style={styles.hwLabel}>CPU</span>
          <span style={styles.hwValue}>{telemetry.system?.cpu_usage ?? "—"}%</span>
        </div>
        <div style={styles.hwCard}>
          <HardDrive size={14} color="#a78bfa" />
          <span style={styles.hwLabel}>VRAM</span>
          <span style={styles.hwValue}>{vitals?.memory?.used_gb ?? "—"} / {vitals?.memory?.total_gb ?? "—"} GB</span>
        </div>
        <div style={styles.hwCard}>
          <Thermometer size={14} color={vitals?.thermal === "Throttled" ? "#f87171" : "#fbbf24"} />
          <span style={styles.hwLabel}>Thermal</span>
          <span style={{ ...styles.hwValue, color: vitals?.thermal === "Throttled" ? "#f87171" : "#fff" }}>{vitals?.thermal ?? "—"}</span>
        </div>
        <div style={styles.hwCard}>
          <Database size={14} color="#60a5fa" />
          <span style={styles.hwLabel}>Disk Free</span>
          <span style={styles.hwValue}>{vitals?.disk?.free_gb ?? "—"} GB</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
        {models.map((model) => {
          const health = modelMetrics[model.key] || { status: "Inactive", avg_confidence: 0 };
          return (
            <div key={model.key} style={{ ...styles.telemetryCard, borderColor: `${model.color}30` }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
                <div style={{ ...styles.opIconWrap, background: `${model.color}12`, border: `1px solid ${model.color}35` }}>
                  <model.Icon size={16} color={model.color} />
                </div>
                <div>
                  <div style={{ fontSize: "0.82rem", fontWeight: "700", color: "#fff" }}>{model.name}</div>
                  <div style={{ fontSize: "0.6rem", color: "rgba(255,255,255,0.25)", fontFamily: "'Courier New', monospace", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    {model.key}
                  </div>
                </div>
              </div>
              
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                {[
                  { label: "Status",      value: health.status,  color: health.status === "Healthy" ? "#10b981" : "#f87171" },
                  { label: "Avg Confidence", value: `${Math.round(health.avg_confidence * 100)}%` },
                  { label: "P95 Latency", value: "—ms" },
                  { label: "Inferences",  value: "—"   },
                ].map((metric) => (
                  <div key={metric.label} style={styles.metricCell}>
                    <span style={styles.metricLabel}>{metric.label}</span>
                    <span style={{ ...styles.metricValue, color: metric.color || "rgba(255,255,255,0.7)" }}>
                      {metric.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function AdminConsolePage() {
  const [activeTab, setActiveTab] = useState("ai-settings");

  // ── AI Settings local state (forwarded to SettingsPanel) ──
  const [provider,         setProvider]         = useState("gemini");
  const [geminiKey,        setGeminiKey]        = useState("");
  const [ollamaUrl,        setOllamaUrl]        = useState("http://localhost:11434");
  const [ollamaModel,      setOllamaModel]      = useState("moondream:latest");

  useEffect(() => {
    setProvider(localStorage.getItem("ai_provider") || "gemini");
    setGeminiKey(localStorage.getItem("gemini_key") || "");
    setOllamaUrl(localStorage.getItem("ollama_url") || process.env.NEXT_PUBLIC_OLLAMA_URL || "http://localhost:11434");
    setOllamaModel(localStorage.getItem("ollama_model") || "moondream:latest");

    const handleStorage = () => {
      setProvider(localStorage.getItem("ai_provider") || "gemini");
      setGeminiKey(localStorage.getItem("gemini_key") || "");
      setOllamaUrl(localStorage.getItem("ollama_url") || "http://localhost:11434");
      setOllamaModel(localStorage.getItem("ollama_model") || "moondream:latest");
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const saveSettings = (k, v) => localStorage.setItem(k, v);

  return (
    <main className="container" style={{ padding: "2.5rem 2rem 4rem" }}>

      {/* ── Page Header ── */}
      <header style={styles.pageHeader}>
        <div>
          <h1 style={styles.pageTitle}>Admin Console</h1>
          <p style={styles.pageSubtitle}>
            Antigravity Engine · Local MLOps Platform
          </p>
        </div>
        <div style={styles.engineBadge}>
          <span style={styles.engineDot} />
          Engine Online
        </div>
      </header>

      {/* ── Glassmorphic Tab Bar ── */}
      <nav style={styles.tabBar} role="tablist" aria-label="Admin Console Sections">
        {TABS.map(({ id, label, Icon }) => {
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              id={`tab-${id}`}
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${id}`}
              onClick={() => setActiveTab(id)}
              style={{
                ...styles.tabBtn,
                ...(isActive ? styles.tabBtnActive : styles.tabBtnInactive),
              }}
            >
              <Icon
                size={15}
                color={isActive ? "var(--accent-base, #60a5fa)" : "rgba(255,255,255,0.4)"}
              />
              <span style={{ marginLeft: "0.4rem" }}>{label}</span>
              {isActive && <div style={styles.tabActiveUnderline} />}
            </button>
          );
        })}
      </nav>

      {/* ── Tab Panels ── */}
      <div
        id={`panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`tab-${activeTab}`}
        style={styles.tabPanel}
      >
        {activeTab === "ai-settings" && (
          <SettingsPanel
            provider={provider}
            setProvider={setProvider}
            geminiKey={geminiKey}
            setGeminiKey={setGeminiKey}
            ollamaUrl={ollamaUrl}
            setOllamaUrl={setOllamaUrl}
            ollamaModel={ollamaModel}
            setOllamaModel={setOllamaModel}
            saveSettings={saveSettings}
          />
        )}

        {activeTab === "data-governance" && <DataGovernanceTab />}
        {activeTab === "model-ops"       && <ModelOpsTab />}
        {activeTab === "telemetry"       && <TelemetryTab />}
      </div>

    </main>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────
const styles = {
  // Page header
  pageHeader: {
    display: "flex",
    alignItems: "flex-end",
    justifyContent: "space-between",
    marginBottom: "2rem",
    flexWrap: "wrap",
    gap: "1rem",
  },
  pageTitle: {
    fontSize: "1.9rem",
    fontWeight: "800",
    color: "#fff",
    letterSpacing: "-0.03em",
    margin: 0,
    lineHeight: 1,
  },
  pageSubtitle: {
    fontSize: "0.72rem",
    color: "rgba(255,255,255,0.33)",
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    marginTop: "0.4rem",
  },
  engineBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: "0.4rem",
    padding: "0.3rem 0.85rem",
    borderRadius: "100px",
    background: "rgba(16,185,129,0.1)",
    border: "1px solid rgba(16,185,129,0.3)",
    color: "#10b981",
    fontSize: "0.68rem",
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  engineDot: {
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    background: "#10b981",
    boxShadow: "0 0 6px #10b981",
  },
  // Tab bar
  tabBar: {
    display: "flex",
    gap: "0.25rem",
    padding: "0.35rem",
    background: "rgba(255,255,255,0.04)",
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
    borderRadius: "14px",
    border: "1px solid rgba(255,255,255,0.08)",
    marginBottom: "2rem",
    overflowX: "auto",
  },
  tabBtn: {
    position: "relative",
    display: "inline-flex",
    alignItems: "center",
    padding: "0.55rem 1.1rem",
    borderRadius: "10px",
    border: "none",
    cursor: "pointer",
    fontSize: "0.8rem",
    fontWeight: "600",
    letterSpacing: "0.01em",
    transition: "background 0.18s ease, color 0.18s ease",
    whiteSpace: "nowrap",
    flexShrink: 0,
  },
  tabBtnActive: {
    background: "rgba(96,165,250,0.14)",
    color: "var(--accent-base, #60a5fa)",
    border: "1px solid rgba(96,165,250,0.28)",
  },
  tabBtnInactive: {
    background: "transparent",
    color: "rgba(255,255,255,0.4)",
  },
  tabActiveUnderline: {
    position: "absolute",
    bottom: "5px",
    left: "50%",
    transform: "translateX(-50%)",
    width: "18px",
    height: "2px",
    borderRadius: "2px",
    background: "var(--accent-base, #60a5fa)",
  },
  // Tab panel
  tabPanel: {
    animation: "fadeIn 0.2s ease",
  },
  // Shell (placeholder) panels
  shellPanel: {
    display: "flex",
    flexDirection: "column",
    gap: "1.5rem",
  },
  shellHeader: {
    marginBottom: "0.5rem",
  },
  shellTitle: {
    fontSize: "1.1rem",
    fontWeight: "700",
    color: "#fff",
    margin: "0 0 0.4rem",
  },
  shellDescription: {
    fontSize: "0.78rem",
    color: "rgba(255,255,255,0.38)",
    margin: 0,
    lineHeight: "1.6",
    maxWidth: "600px",
  },
  shellGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "1rem",
  },
  shellCard: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: "14px",
    padding: "1.25rem",
  },
  shellCardHeader: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    marginBottom: "0.75rem",
  },
  shellCardTitle: {
    fontSize: "0.82rem",
    fontWeight: "700",
    color: "#fff",
    flex: 1,
  },
  shellBadge: {
    fontSize: "0.58rem",
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    padding: "2px 7px",
    borderRadius: "100px",
    border: "1px solid",
    flexShrink: 0,
  },
  shellCardBody: {
    fontSize: "0.73rem",
    color: "rgba(255,255,255,0.38)",
    lineHeight: "1.6",
    margin: 0,
  },
  // Data Governance
  dataCard: {
    borderRadius: "14px",
    padding: "1.25rem",
    border: "1px solid",
  },
  actionRail: {
    background: "rgba(255,255,255,0.025)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: "14px",
    padding: "1.25rem",
  },
  actionRailHeader: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    marginBottom: "1rem",
  },
  actionRailLabel: {
    fontSize: "0.7rem",
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "rgba(255,255,255,0.32)",
    fontWeight: "600",
    flex: 1,
  },
  wiredBadge: {
    fontSize: "0.58rem",
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    padding: "2px 7px",
    borderRadius: "100px",
    border: "1px solid rgba(255,255,255,0.12)",
    color: "rgba(255,255,255,0.25)",
  },
  actionBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: "0.4rem",
    padding: "0.5rem 1rem",
    borderRadius: "10px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid",
    fontSize: "0.76rem",
    fontWeight: "600",
    cursor: "not-allowed",
    opacity: 0.5,
    transition: "opacity 0.2s",
  },
  // Model Ops
  opRow: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    padding: "1.25rem",
    background: "rgba(255,255,255,0.025)",
    border: "1px solid",
    borderRadius: "14px",
  },
  opIconWrap: {
    width: "44px",
    height: "44px",
    borderRadius: "12px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  opTriggerBtn: {
    width: "36px",
    height: "36px",
    borderRadius: "10px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "not-allowed",
    opacity: 0.45,
    flexShrink: 0,
  },
  // Telemetry
  telemetryCard: {
    background: "rgba(255,255,255,0.025)",
    border: "1px solid",
    borderRadius: "16px",
    padding: "1.25rem",
  },
  metricCell: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: "8px",
    padding: "0.5rem 0.65rem",
  },
  metricLabel: {
    fontSize: "0.58rem",
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "rgba(255,255,255,0.25)",
    fontWeight: "600",
  },
  metricValue: {
    fontSize: "0.82rem",
    fontWeight: "700",
    fontFamily: "'Courier New', monospace",
  },
  // Hardware Metrics
  hwCard: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    gap: "0.6rem",
    padding: "0.75rem 1rem",
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: "12px",
  },
  hwLabel: {
    fontSize: "0.7rem",
    color: "rgba(255,255,255,0.35)",
    fontWeight: "600",
    flex: 1,
  },
  hwValue: {
    fontSize: "0.85rem",
    fontWeight: "800",
    color: "#fff",
    fontFamily: "'Courier New', monospace",
  },
  // Prompt Playground
  promptCard: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    padding: "1rem 1.25rem",
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: "12px",
    transition: "transform 0.2s ease",
  },
  playgroundInput: {
    background: "rgba(0,0,0,0.2)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: "8px",
    padding: "0.75rem",
    color: "#fff",
    fontSize: "0.85rem",
    fontFamily: "'Courier New', monospace",
    outline: "none",
    width: "100%",
  },
  miniMetric: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    background: "rgba(0,0,0,0.2)",
    padding: "0.6rem",
    borderRadius: "8px",
    textAlign: "center",
  },
  miniLabel: {
    fontSize: "0.55rem",
    textTransform: "uppercase",
    color: "rgba(255,255,255,0.3)",
    fontWeight: "700",
  },
  miniValue: {
    fontSize: "0.9rem",
    fontWeight: "800",
    color: "#fff",
  },
  iconBtn: {
    width: "32px",
    height: "32px",
    borderRadius: "8px",
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    color: "rgba(255,255,255,0.6)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  recBanner: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    padding: "0.85rem 1.25rem",
    borderRadius: "14px",
    border: "1px solid",
  },
};
