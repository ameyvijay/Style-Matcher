import Link from "next/link";

export default function ToolCard({ href, title, description, icon: Icon }) {
  return (
    <Link href={href} style={{ textDecoration: "none", color: "inherit" }}>
      <div 
        className="glass-panel" 
        style={{ 
          padding: "2rem", 
          height: "100%", 
          display: "flex", 
          flexDirection: "column", 
          gap: "1rem", 
          transition: "all 0.2s ease" 
        }} 
        onMouseOver={(e) => e.currentTarget.style.borderColor = "var(--accent-base)"} 
        onMouseOut={(e) => e.currentTarget.style.borderColor = "var(--glass-border)"}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Icon color="var(--accent-hover)" size={28} />
          <h2 style={{ margin: 0 }}>{title}</h2>
        </div>
        <p style={{ color: "var(--text-secondary)", flex: 1, margin: 0 }}>
          {description}
        </p>
      </div>
    </Link>
  );
}
