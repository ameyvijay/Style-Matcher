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
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
                const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
                   const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
  const { Zap, RefreshCw, FlaskConical, ChevronRight } = require("lucide-react");

  const ops = [
    {
      Icon: RefreshCw,
      title: "LoRA Fine-Tune",
      status: "Idle",
      color: "#10b981",
      body: "Trigger incremental LoRA weight updates from the latest accepted/rejected annotation batch.",
      /** TODO: Wire to POST /api/model/lora-update */
      endpoint: "POST /api/model/lora-update",
    },
    {
      Icon: Zap,
      title: "RAG Index Rebuild",
      status: "Idle",
      color: "#a78bfa",
      body: "Re-index all accepted exemplars into ChromaDB and refresh the semantic search vectors.",
      /** TODO: Wire to POST /api/model/rag-rebuild */
      endpoint: "POST /api/model/rag-rebuild",
    },
    {
      Icon: FlaskConical,
      title: "Staging Evaluation",
      status: "Not Run",
      color: "#f59e0b",
      body: "Run the held-out eval split through the current model and report accuracy + confusion matrix.",
      /** TODO: Wire to POST /api/model/staging-eval */
      endpoint: "POST /api/model/staging-eval",
    },
  ];

  return (
    <div style={styles.shellPanel}>
      <div style={styles.shellHeader}>
        <h2 style={styles.shellTitle}>Model Ops</h2>
        <p style={styles.shellDescription}>
          Trigger LoRA/RAG updates, inspect the AI Recommendation Engine state, and run Staging Evals.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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
              <code style={{ fontSize: "0.6rem", color: "rgba(255,255,255,0.2)", fontFamily: "'Courier New', monospace", marginTop: "6px", display: "block" }}>
                {/* TODO: endpoint={op.endpoint} */}
                Endpoint: {op.endpoint}
              </code>
            </div>
            <button style={{ ...styles.opTriggerBtn, borderColor: `${op.color}44`, color: op.color }} disabled>
              <ChevronRight size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Telemetry Tab ─────────────────────────────────────────────────────────────
function TelemetryTab() {
  const { Eye, Sparkles, ScanLine, MessageSquare, Cpu, HardDrive } = require("lucide-react");
  const [telemetry, setTelemetry] = useState({ system: {}, models: {} });

  useEffect(() => {
    async function fetchTelemetry() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${baseUrl}/api/admin/telemetry`);
        const data = await res.json();
        setTelemetry(data);
      } catch (e) {
        console.error("Failed to fetch telemetry:", e);
      }
    }
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 5000);
    return () => clearInterval(interval);
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
      <div style={{ display: "flex", gap: "1rem", marginBottom: "2rem" }}>
        <div style={styles.hwCard}>
          <Cpu size={14} color="var(--accent-base)" />
          <span style={styles.hwLabel}>CPU Usage</span>
          <span style={styles.hwValue}>{telemetry.system?.cpu_usage ?? "—"}%</span>
        </div>
        <div style={styles.hwCard}>
          <HardDrive size={14} color="#a78bfa" />
          <span style={styles.hwLabel}>Unified Memory</span>
          <span style={styles.hwValue}>{telemetry.system?.memory_usage ?? "—"}%</span>
        </div>
        <div style={{ ...styles.hwCard, borderLeft: telemetry.system?.mps_available ? "3px solid #10b981" : "3px solid #f87171" }}>
          <Sparkles size={14} color="#10b981" />
          <span style={styles.hwLabel}>M4 Metal (MPS)</span>
          <span style={styles.hwValue}>{telemetry.system?.mps_available ? "Active" : "Disabled"}</span>
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
  const [ollamaModel,      setOllamaModel]      = useState("gemma4:e4b");
  const [benchmarkFolder,  setBenchmarkFolder]  = useState("");

  useEffect(() => {
    setProvider(localStorage.getItem("ai_provider") || "gemini");
    setGeminiKey(localStorage.getItem("gemini_key") || "");
    setOllamaUrl(localStorage.getItem("ollama_url") || process.env.NEXT_PUBLIC_OLLAMA_URL || "http://localhost:11434");
    setOllamaModel(localStorage.getItem("ollama_model") || "gemma4:e4b");
    setBenchmarkFolder(localStorage.getItem("benchmark_folder") || "");

    const handleStorage = () => {
      setProvider(localStorage.getItem("ai_provider") || "gemini");
      setGeminiKey(localStorage.getItem("gemini_key") || "");
      setOllamaUrl(localStorage.getItem("ollama_url") || "http://localhost:11434");
      setOllamaModel(localStorage.getItem("ollama_model") || "gemma4:e4b");
      setBenchmarkFolder(localStorage.getItem("benchmark_folder") || "");
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
            benchmarkFolder={benchmarkFolder}
            setBenchmarkFolder={setBenchmarkFolder}
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
};
