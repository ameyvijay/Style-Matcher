"use client";

import { Info } from "lucide-react";

export default function VersionBadge() {
  return (
    <div className="version-badge">
      <Info size={14} />
      <span>v1.2.0-M4 (Built: 2026-04-11 13:38)</span>
      <style jsx>{`
        .version-badge {
          position: fixed;
          bottom: 20px;
          right: 20px;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 14px;
          background: rgba(255, 255, 255, 0.05);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 100px;
          color: rgba(255, 255, 255, 0.6);
          font-family: inherit;
          font-size: 0.75rem;
          font-weight: 600;
          letter-spacing: 0.05em;
          z-index: 9999;
          pointer-events: none;
          transition: all 0.3s ease;
          animation: slideUpFade 0.8s ease-out forwards;
        }

        @keyframes slideUpFade {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
