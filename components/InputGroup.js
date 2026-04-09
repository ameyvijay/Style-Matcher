export default function InputGroup({ label, icon: Icon, children, description }) {
  return (
    <div className="input-group">
      <label className="label" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        {Icon && <Icon size={16} />} 
        {label}
      </label>
      {children}
      {description && (
        <p style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
          {description}
        </p>
      )}
    </div>
  );
}
