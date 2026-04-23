"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Lock, Unlock, Image, Camera, Activity, Settings, LayoutDashboard, CheckCircle } from "lucide-react";

export default function Navigation() {
  const [isOpen, setIsOpen] = useState(false);
  const [isLocal, setIsLocal] = useState(false);
  const [engineOnline, setEngineOnline] = useState(false);

  const checkEngine = async () => {
    try {
      const hostname = typeof window !== 'undefined' ? (window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname) : '127.0.0.1';
      const baseUrl = (process.env.NEXT_PUBLIC_API_URL || `http://${hostname}:8000`).trim();
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
    { name: "HiTL Swiper", href: "/", icon: <Image size={18} />, requiresLocal: false },
    { name: "Style Matcher", href: "/style-match", icon: <Camera size={18} />, requiresLocal: false },
    { name: "Background Remover", href: "/remove-bg", icon: <Image size={18} />, requiresLocal: false },
    { name: "Analytics Dashboard", href: "/dashboard", icon: <Activity size={18} />, requiresLocal: false },
    { name: "Batch Studio", href: "/batch-studio", icon: <LayoutDashboard size={18} />, requiresLocal: true },
    { name: "System Config", href: "/landing", icon: <Settings size={18} />, requiresLocal: true },
  ];

  return (
    <>
      <motion.button 
        onClick={toggleMenu}
        drag
        dragConstraints={{ left: 0, top: 0, right: 300, bottom: 600 }}
        dragElastic={0.1}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        style={{
          position: "fixed",
          top: "1.5rem",
          left: "1.5rem",
          zIndex: 9999,
          background: "rgba(0,0,0,0.7)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,0.15)",
          borderRadius: "16px",
          width: "48px",
          height: "48px",
          cursor: "grab",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)"
        }}
      >
        {isOpen ? <X size={22} /> : <Menu size={22} />}
      </motion.button>

      <motion.div 
        initial={false}
        animate={{ x: isOpen ? 0 : -300 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          bottom: 0,
          width: "300px",
          background: "rgba(10, 10, 10, 0.95)",
          backdropFilter: "blur(20px)",
          borderRight: "1px solid rgba(255,255,255,0.1)",
          zIndex: 9998,
          padding: "5rem 1rem 2rem 1rem",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
          boxShadow: "20px 0 80px rgba(0,0,0,0.5)"
        }}
      >
        <div style={{ padding: "0 1rem", marginBottom: "1rem", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "2px", color: "rgba(255,255,255,0.3)", fontWeight: "700" }}>
          Engine Navigation
        </div>

        {links.map((link) => {
          const locked = link.requiresLocal && !isLocal;
          
          return (
            <div key={link.name}>
              {locked ? (
                <div style={{ display: "flex", alignItems: "center", gap: "0.85rem", padding: "0.85rem 1.25rem", color: "#444", cursor: "not-allowed", borderRadius: "12px", background: "rgba(255,255,255,0.02)" }}>
                  {link.icon}
                  <span style={{ flex: 1, fontSize: "0.9rem" }}>{link.name}</span>
                  <Lock size={12} color="#333" />
                </div>
              ) : (
                <Link 
                  href={link.href}
                  onClick={() => setIsOpen(false)}
                  style={{ display: "flex", alignItems: "center", gap: "0.85rem", padding: "0.85rem 1.25rem", color: "rgba(255,255,255,0.8)", textDecoration: "none", borderRadius: "12px", transition: "all 0.2s ease" }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                    e.currentTarget.style.color = "#fff";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "rgba(255,255,255,0.8)";
                  }}
                >
                  {link.icon}
                  <span style={{ flex: 1, fontSize: "0.9rem" }}>{link.name}</span>
                </Link>
              )}
            </div>
          );
        })}

        <div style={{ marginTop: "auto", padding: "1.25rem", background: "rgba(255,255,255,0.03)", borderRadius: "14px", display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.75rem", color: "rgba(255,255,255,0.5)", border: "1px solid rgba(255,255,255,0.05)" }}>
          {isLocal ? <Unlock size={14} color="#4ade80" /> : <Lock size={14} color="#f87171" />}
          <div style={{ flex: 1, lineHeight: "1.2" }}>
            <div style={{ fontWeight: "700", color: isLocal ? "#4ade80" : "#f87171", fontSize: "0.65rem", textTransform: "uppercase", marginBottom: "2px" }}>
              {isLocal ? "Local Mode" : "Cloud Mode"}
            </div>
            {isLocal ? "M4 Compute Active" : "Read-Only Proxy"}
          </div>
          {engineOnline && <CheckCircle size={14} color="#4ade80" />}
        </div>
      </motion.div>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={toggleMenu}
            style={{ 
              position: "fixed", 
              inset: 0, 
              background: "rgba(0,0,0,0.6)", 
              backdropFilter: "blur(8px)",
              zIndex: 9997, 
              cursor: "pointer" 
            }}
          />
        )}
      </AnimatePresence>
    </>
  );
}

