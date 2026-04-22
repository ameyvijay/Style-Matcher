"use client";

import { Info } from "lucide-react";

const VersionBadge = () => {
  return (
    <div className="version-badge">
      <Info size={14} />
      <span>v2.1.5 — Antigravity Intelligence (Built: 2026-04-21)</span>
      <style jsx>{`
        .version-badge {
          position: fixed;
          bottom: 1rem;
          right: 1rem;
          padding: 0.4rem 0.8rem;
          background: rgba(255, 255, 255, 0.05);
          backdrop-filter: blur(8px);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 99px;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.75rem;
          color: var(--text-secondary);
          z-index: 1000;
          pointer-events: none;
        }
      `}</style>
    </div>
  );
};

export default VersionBadge;
