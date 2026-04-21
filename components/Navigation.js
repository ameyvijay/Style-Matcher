"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, X, Lock, Unlock, Image, Camera, Activity, Settings, LayoutDashboard, CheckCircle } from "lucide-react";

export default function Navigation() {
  const [isOpen, setIsOpen] = useState(false);
  const [isLocal, setIsLocal] = useState(false);
  const [engineOnline, setEngineOnline] = useState(false);

  const checkEngine = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${baseUrl}/api/health`, { cache: 'no-store' });
      setEngineOnline(res.ok);
    } catch (e) {
      setEngineOnline(false);
    }
  };

  useEffect(() => {
    // Determine isLocal on client mount to prevent hydration mismatch
    const hostname = window.location.hostname;
    const local = (
      hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname.endsWith(".local") ||
      hostname.startsWith("192.168.") ||
      hostname.startsWith("10.0.")
    );
    setIsLocal(local);

    // Initial check
    checkEngine();

    // Heartbeat polling
    const timer = setInterval(checkEngine, 10000);
    return () => clearInterval(timer);
  }, []);
  const toggleMenu = () => setIsOpen(!isOpen);

  // Link configs
  const links = [
    { name: "RLHF Swiper", href: "/", icon: <Image size={18} />, requiresLocal: false },
    { name: "Style Matcher", href: "/style-match", icon: <Camera size={18} />, requiresLocal: false },
    { name: "Background Remover", href: "/remove-bg", icon: <Image size={18} />, requiresLocal: false },
    { name: "Analytics Dashboard", href: "/dashboard", icon: <Activity size={18} />, requiresLocal: false },
    { name: "Batch Studio", href: "/batch-studio", icon: <LayoutDashboard size={18} />, requiresLocal: true },
    { name: "System Config", href: "/landing", icon: <Settings size={18} />, requiresLocal: true },
  ];

  return (
    <>
      <button 
        onClick={toggleMenu}
        style={{
          position: "fixed",
          top: "1rem",
          left: "1rem",
          zIndex: 9999,
          background: "rgba(0,0,0,0.6)",
          backdropFilter: "blur(10px)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: "50%",
          padding: "0.75rem",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white"
        }}
      >
        {isOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      <div 
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          bottom: 0,
          width: "300px",
          background: "var(--bg-panel)",
          borderRight: "1px solid var(--glass-border)",
          transform: isOpen ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          zIndex: 9998,
          padding: "5rem 1rem 2rem 1rem",
          display: "flex",
          flexDirection: "column",
          gap: "1rem"
        }}
      >
        <div style={{ padding: "0 1rem", marginBottom: "1rem", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "1px", color: "var(--text-secondary)" }}>
          Navigation
        </div>

        {links.map((link) => {
          const locked = link.requiresLocal && !isLocal;
          
          return (
            <div key={link.name}>
              {locked ? (
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "1rem", color: "#666", cursor: "not-allowed", borderRadius: "8px", background: "rgba(255,255,255,0.02)" }}>
                  {link.icon}
                  <span style={{ flex: 1 }}>{link.name}</span>
                  <Lock size={14} color="#666" />
                </div>
              ) : (
                <Link 
                  href={link.href}
                  onClick={() => setIsOpen(false)}
                  style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "1rem", color: "white", textDecoration: "none", borderRadius: "8px", transition: "background 0.2s" }}
                  onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.1)"}
                  onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                >
                  {link.icon}
                  <span style={{ flex: 1 }}>{link.name}</span>
                </Link>
              )}
            </div>
          );
        })}

        <div style={{ marginTop: "auto", padding: "1rem", background: "rgba(0,0,0,0.3)", borderRadius: "8px", display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.8rem", color: "var(--text-secondary)", borderLeft: engineOnline ? "3px solid #4ade80" : "none" }}>
          {isLocal ? <Unlock size={14} color="#4ade80" /> : <Lock size={14} color="#f87171" />}
          <div style={{ flex: 1 }}>
            {isLocal ? "Local Compute Engine" : "Cloud Remote (Read-Only)"}
          </div>
          {engineOnline && <CheckCircle size={14} color="#4ade80" />}
        </div>
      </div>

      {isOpen && (
        <div 
          onClick={toggleMenu}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 9997, cursor: "pointer" }}
        />
      )}
    </>
  );
}
