export default function LangToggle({ lang, onChange, accent = "#e8400c" }) {
  return (
    <div style={{
      display: "inline-flex",
      background: "#0d0d0d",
      border: "1px solid #222",
      borderRadius: 5,
      overflow: "hidden",
      padding: 2,
    }}>
      {["en", "pt"].map(l => (
        <button
          key={l}
          onClick={() => onChange(l)}
          style={{
            background: lang === l ? accent : "transparent",
            color: lang === l ? "#fff" : "#666",
            border: "none",
            padding: "4px 10px",
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.08em",
            cursor: lang === l ? "default" : "pointer",
            borderRadius: 3,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
