import { useState, useEffect, useRef, useMemo } from "react";
import GraphViz3D from "./components/GraphViz3D.jsx";
import ExportMenu from "./components/ExportMenu.jsx";
import LangToggle from "./components/LangToggle.jsx";
import { makeT, getInitialLang, saveLang } from "./i18n.js";

const IS_DEV = window.location.port === "5173";
const API = IS_DEV ? "http://localhost:8000" : "";
const WS_BASE = IS_DEV ? "ws://localhost:8000" : `ws://${window.location.host}`;

const C = {
  bg: "#070707",
  bg2: "#0d0d0d",
  bg3: "#111",
  border: "#1a1a1a",
  borderLight: "#222",
  text: "#e8e8e8",
  textDim: "#888",
  textMute: "#555",
  textFaint: "#333",
  accent: "#e8400c",
  accentDim: "#e8400c30",
  green: "#00d4a4",
  yellow: "#ffd700",
  orange: "#ff8c00",
  red: "#ff3b3b",
  blue: "#4a9eff",
};

const SEV = {
  critical: { color: C.red, label: "CRITICAL", icon: "▲" },
  major: { color: C.orange, label: "MAJOR", icon: "◆" },
  minor: { color: C.yellow, label: "MINOR", icon: "●" },
  suggestion: { color: C.green, label: "SUGGEST", icon: "◇" },
};


// ── Primitives ─────────────────────────────────────────────────────────

function Pill({ children, color = C.textDim, bg }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 7px",
      fontSize: 10,
      fontFamily: "'JetBrains Mono', monospace",
      letterSpacing: "0.06em",
      color,
      background: bg || `${color}15`,
      border: `1px solid ${color}30`,
      borderRadius: 3,
      fontWeight: 600,
    }}>{children}</span>
  );
}

function SectionLabel({ num, label, icon, noMargin }) {
  return (
    <div style={{
      fontSize: 10, color: C.accent,
      letterSpacing: "0.12em", marginBottom: noMargin ? 0 : 14,
      display: "flex", alignItems: "center", gap: 8,
      fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
    }}>
      <span style={{ color: C.textFaint }}>{num}</span>
      <span style={{ width: 12, height: 1, background: C.accent }} />
      <span>{label}</span>
      {icon && <span style={{ marginLeft: "auto", color: C.textFaint }}>{icon}</span>}
    </div>
  );
}

function StageNode({ stage, status, elapsed, data, t }) {
  const colorMap = { pending: C.textFaint, running: C.accent, done: C.green, error: C.red };
  const color = colorMap[status] || C.textFaint;

  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 12,
      padding: "10px 12px",
      background: status === "running" ? `${C.accent}08` : "transparent",
      borderLeft: `2px solid ${color}`,
      borderRadius: "0 6px 6px 0",
      transition: "all 0.3s",
    }}>
      <div style={{
        width: 22, height: 22, borderRadius: "50%",
        border: `1.5px solid ${color}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0, marginTop: 1,
      }}>
        {status === "running" && (
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: color, animation: "pulse 1.2s infinite",
          }} />
        )}
        {status === "done" && <span style={{ color, fontSize: 11, fontWeight: 700 }}>✓</span>}
        {status === "error" && <span style={{ color, fontSize: 11, fontWeight: 700 }}>✕</span>}
        {status === "pending" && <span style={{ color, fontSize: 9 }}>○</span>}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
          <span style={{
            color: status === "pending" ? C.textFaint : C.text,
            fontSize: 13, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace",
          }}>{stage.label}</span>
          {elapsed != null && <Pill color={C.textMute}>{elapsed.toFixed(2)}s</Pill>}
        </div>
        <div style={{ color: C.textMute, fontSize: 11 }}>{stage.desc}</div>

        {data && status !== "pending" && (
          <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
            {data.context_files && (
              <div style={{ fontSize: 10, fontFamily: "monospace", color: C.textMute }}>
                {t("stage_context_files", { n: data.context_files.length })}
              </div>
            )}
            {data.queries && data.queries.length > 0 && (
              <div style={{ fontSize: 10, fontFamily: "monospace", color: C.textMute }}>
                {t("stage_queries")}: {data.queries.slice(0, 2).map(q => `"${q.slice(0, 20)}…"`).join(", ")}
              </div>
            )}
            {data.raw_issues_count != null && (
              <div style={{ fontSize: 10, fontFamily: "monospace", color: C.textMute }}>
                {t("stage_raw_issues", { n: data.raw_issues_count })}
              </div>
            )}
            {data.validated != null && (
              <div style={{ fontSize: 10, fontFamily: "monospace" }}>
                <span style={{ color: C.green }}>✓ {t("stage_validated", { n: data.validated })}</span>
                <span style={{ color: C.textFaint, margin: "0 6px" }}>·</span>
                <span style={{ color: C.red }}>✕ {t("stage_filtered", { n: data.rejected })}</span>
              </div>
            )}
            {data.stats && (
              <div style={{ display: "flex", gap: 4, marginTop: 2, flexWrap: "wrap" }}>
                {Object.entries(data.stats).filter(([k]) => k !== "filtered_by_critic" && k !== "total").map(([k, v]) => v > 0 && (
                  <Pill key={k} color={SEV[k]?.color || C.textMute}>
                    {SEV[k]?.label || k}: {v}
                  </Pill>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatBox({ label, value, color = C.textDim }) {
  return (
    <div style={{
      flex: "1 1 80px", background: C.bg2,
      border: `1px solid ${color}25`, borderRadius: 6,
      padding: "10px 14px", textAlign: "left",
    }}>
      <div style={{
        fontSize: 22, fontWeight: 700, color,
        fontFamily: "'JetBrains Mono', monospace", lineHeight: 1,
      }}>{value}</div>
      <div style={{
        fontSize: 9, color: C.textMute, marginTop: 4,
        letterSpacing: "0.08em", fontWeight: 600,
      }}>{label}</div>
    </div>
  );
}

function IssueCard({ issue, t }) {
  const [open, setOpen] = useState(false);
  const sev = SEV[issue.severity] || SEV.suggestion;

  return (
    <div style={{
      borderLeft: `3px solid ${sev.color}`,
      background: C.bg2, marginBottom: 6,
      borderRadius: "0 6px 6px 0", overflow: "hidden",
      border: `1px solid ${C.border}`, borderLeftWidth: 3,
    }}>
      <div onClick={() => setOpen(!open)} style={{
        padding: "10px 14px", cursor: "pointer",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <span style={{ color: sev.color, fontSize: 11 }}>{sev.icon}</span>
        <Pill color={sev.color}>{sev.label}</Pill>
        <span style={{ fontSize: 11, color: C.textMute, fontFamily: "monospace" }}>{issue.file}</span>
        {issue.line && <span style={{ fontSize: 11, color: C.textFaint, fontFamily: "monospace" }}>:L{issue.line}</span>}
        <span style={{ color: C.text, fontSize: 13, flex: 1, marginLeft: 4 }}>{issue.description}</span>
        <span style={{ color: C.textFaint, fontSize: 10 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "0 14px 12px", borderTop: `1px solid ${C.border}` }}>
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 10, color: C.textMute, marginBottom: 4, letterSpacing: "0.08em", fontWeight: 600 }}>
              {t("justification")}
            </div>
            <div style={{ color: C.textDim, fontSize: 12, lineHeight: 1.6 }}>{issue.justification}</div>
          </div>
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 10, color: C.textMute, marginBottom: 4, letterSpacing: "0.08em", fontWeight: 600 }}>
              {t("suggestion")}
            </div>
            <div style={{ color: C.green, fontSize: 12, lineHeight: 1.6, fontFamily: "monospace" }}>{issue.suggestion}</div>
          </div>
          {issue.category && (
            <div style={{ marginTop: 8 }}>
              <Pill color={C.blue}>{issue.category}</Pill>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────

export default function App() {
  // i18n
  const [lang, setLang] = useState(getInitialLang());
  const t = useMemo(() => makeT(lang), [lang]);
  const handleLangChange = (newLang) => {
    setLang(newLang);
    saveLang(newLang);
  };

  const PIPELINE_STAGES = useMemo(() => [
    { id: "parse", label: t("stage_parse_label"), desc: t("stage_parse_desc") },
    { id: "contextualize", label: t("stage_contextualize_label"), desc: t("stage_contextualize_desc") },
    { id: "review", label: t("stage_review_label"), desc: t("stage_review_desc") },
    { id: "critic", label: t("stage_critic_label"), desc: t("stage_critic_desc") },
    { id: "report", label: t("stage_report_label"), desc: t("stage_report_desc") },
  ], [lang]);

  const [config, setConfig] = useState(null);
  const [repos, setRepos] = useState([]);
  const [activeRepo, setActiveRepo] = useState(null);
  const [activeGraph, setActiveGraph] = useState(null);
  const [repoPath, setRepoPath] = useState("");
  const [diff, setDiff] = useState("");

  const [indexJob, setIndexJob] = useState(null);
  const [reviewJob, setReviewJob] = useState(null);
  const [stageStates, setStageStates] = useState({});
  const [stageData, setStageData] = useState({});
  const [reviewResult, setReviewResult] = useState(null);
  const [error, setError] = useState(null);
  const [indexLog, setIndexLog] = useState([]);
  const [highlightFiles, setHighlightFiles] = useState([]);

  const wsRef = useRef(null);

  useEffect(() => {
    fetchConfig();
    fetchRepos();
  }, []);

  useEffect(() => {
    if (!activeRepo) {
      setActiveGraph(null);
      return;
    }
    fetch(`${API}/repos/${activeRepo}/graph`)
      .then(r => r.json())
      .then(setActiveGraph)
      .catch(() => setActiveGraph(null));
  }, [activeRepo]);

  useEffect(() => {
    if (reviewResult?.context?.files) {
      console.log("[RepoMind] Final highlight files:", reviewResult.context.files);
      setHighlightFiles(reviewResult.context.files);
    } else {
      setHighlightFiles([]);
    }
  }, [reviewResult]);

  async function fetchConfig() {
    try {
      const r = await fetch(`${API}/config`);
      setConfig(await r.json());
    } catch {}
  }

  async function fetchRepos() {
    try {
      const r = await fetch(`${API}/repos`);
      const d = await r.json();
      setRepos(d.repos || []);
    } catch {}
  }

  function connectWS(jobId, onEvent, onComplete, onError) {
    if (wsRef.current) try { wsRef.current.close(); } catch {}
    const wsUrl = `${WS_BASE}/ws/jobs/${jobId}`;
    console.log("[RepoMind] Conectando WebSocket:", wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    let resolved = false;
    let pollTimer = null;

    const finalize = (kind, data) => {
      if (resolved) return;
      resolved = true;
      if (pollTimer) clearInterval(pollTimer);
      try { ws.close(); } catch {}
      if (kind === "complete") onComplete(data);
      else onError(typeof data === "string" ? data : (data?.error || "erro desconhecido"));
    };

    ws.onopen = () => console.log("[RepoMind] WS aberto");
    ws.onclose = (e) => {
      console.log("[RepoMind] WS fechado", e.code, e.reason);
      if (!resolved) {
        console.log("[RepoMind] WS fechou sem resolver. Iniciando polling REST...");
        pollTimer = setInterval(async () => {
          try {
            const r = await fetch(`${API}/jobs/${jobId}`);
            if (!r.ok) return;
            const job = await r.json();
            if (job.status === "done") {
              finalize("complete", job.result);
            } else if (job.status === "error") {
              finalize("error", job.error || "erro");
            }
          } catch {}
        }, 1000);
        // Hard timeout: 5min
        setTimeout(() => {
          if (!resolved) finalize("error", "Timeout esperando resposta do backend");
        }, 300_000);
      }
    };
    ws.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data);
        console.log("[RepoMind] WS event:", evt.type, evt.data);
        if (evt.type === "complete") finalize("complete", evt.data);
        else if (evt.type === "error") finalize("error", evt.data?.error || "erro");
        else onEvent(evt);
      } catch (err) {
        console.error("[RepoMind] WS parse error:", err, e.data);
      }
    };
    ws.onerror = (e) => {
      console.error("[RepoMind] WS error:", e);
    };
  }

  async function handleIndex() {
    if (!repoPath.trim()) return;
    setError(null);
    setIndexLog([]);
    console.log("[RepoMind] Iniciando indexação:", repoPath);

    try {
      const r = await fetch(`${API}/repos/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_path: repoPath }),
      });
      console.log("[RepoMind] /repos/index response:", r.status);
      if (!r.ok) {
        const txt = await r.text();
        setError(`Erro ${r.status}: ${txt}`);
        return;
      }
      const d = await r.json();
      console.log("[RepoMind] job_id recebido:", d.job_id);
      setIndexJob(d.job_id);
      setIndexLog([{ data: { message: `Job iniciado: ${d.job_id}` } }]);
      connectWS(d.job_id,
        (evt) => setIndexLog(prev => [...prev, evt]),
        (result) => {
          console.log("[RepoMind] Indexação completa:", result);
          setIndexJob(null);
          fetchRepos().then(() => setActiveRepo(result.collection));
        },
        (err) => {
          console.error("[RepoMind] Erro na indexação:", err);
          setIndexJob(null);
          setError(err);
        }
      );
    } catch(e) {
      console.error("[RepoMind] Falha no fetch:", e);
      setError(`Não conectou no backend (${API || 'mesma origem'}). Backend rodando em :8000? Erro: ${e.message}`);
    }
  }

  async function handleReview() {
    if (!activeRepo || !diff.trim()) return;
    setError(null);
    setReviewResult(null);
    setStageStates({});
    setStageData({});
    setHighlightFiles([]);

    const r = await fetch(`${API}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: activeRepo, diff, lang }),
    });
    const d = await r.json();
    setReviewJob(d.job_id);

    connectWS(d.job_id,
      (evt) => {
        const [stage, action] = evt.type.split(":");
        if (PIPELINE_STAGES.find(s => s.id === stage)) {
          setStageStates(prev => ({ ...prev, [stage]: action === "done" ? "done" : "running" }));
          if (action === "done") {
            setStageData(prev => ({ ...prev, [stage]: { ...evt.data, _elapsed: evt.data.elapsed } }));
          }
          if (stage === "contextualize" && action === "done" && evt.data.context_files) {
            console.log("[RepoMind] Highlighting files in graph:", evt.data.context_files);
            setHighlightFiles(evt.data.context_files);
          }
        }
      },
      (result) => { setReviewJob(null); setReviewResult(result); },
      (err) => { setReviewJob(null); setError(err); }
    );
  }

  const activeRepoMeta = useMemo(
    () => repos.find(r => r.id === activeRepo),
    [repos, activeRepo]
  );

  const isIndexing = !!indexJob;
  const isReviewing = !!reviewJob;
  const issues = reviewResult?.report?.issues || [];

  return (
    <div style={{
      minHeight: "100vh", background: C.bg, color: C.text,
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.9); }
        }
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        textarea, input, select {
          background: ${C.bg2};
          border: 1px solid ${C.border};
          color: ${C.text};
          border-radius: 6px;
          padding: 10px 12px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          outline: none;
          transition: all 0.15s;
          width: 100%;
        }
        textarea:focus, input:focus, select:focus {
          border-color: ${C.accent};
          box-shadow: 0 0 0 3px ${C.accent}15;
        }
        button {
          cursor: pointer; border: none; border-radius: 5px;
          font-family: 'JetBrains Mono', monospace;
          font-weight: 700; font-size: 11px;
          letter-spacing: 0.08em;
          transition: all 0.15s;
          padding: 10px 20px;
        }
        button:disabled { cursor: not-allowed; opacity: 0.4; }
        button:not(:disabled):hover { transform: translateY(-1px); }
        button:not(:disabled):active { transform: translateY(0); }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: ${C.bg}; }
        ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: ${C.borderLight}; }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header style={{
        borderBottom: `1px solid ${C.border}`,
        padding: "14px 28px",
        display: "flex", alignItems: "center", gap: 14,
        background: `${C.bg}f0`, backdropFilter: "blur(8px)",
        position: "sticky", top: 0, zIndex: 10,
      }}>
        <div style={{
          width: 30, height: 30,
          background: `linear-gradient(135deg, ${C.accent}, #ff6b3d)`,
          borderRadius: 5,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 14, fontWeight: 700, color: "#fff",
        }}>R</div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: C.text, lineHeight: 1, letterSpacing: "-0.01em" }}>
            RepoMind
          </div>
          <div style={{ fontSize: 9, color: C.textMute, letterSpacing: "0.1em", marginTop: 3, fontFamily: "monospace" }}>
            {t("tagline")}
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 12, alignItems: "center" }}>
          <LangToggle lang={lang} onChange={handleLangChange} accent={C.accent} />
          {config && (
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <Pill color={C.blue}>{config.provider?.toUpperCase()}</Pill>
              <span style={{ fontSize: 10, color: C.textMute, fontFamily: "monospace" }}>
                {config.model}
              </span>
            </div>
          )}
          <div style={{
            width: 6, height: 6, borderRadius: "50%",
            background: C.green, boxShadow: `0 0 8px ${C.green}`,
          }} />
          <span style={{ fontSize: 10, color: C.textMute, fontFamily: "monospace", letterSpacing: "0.06em" }}>
            {t("online")}
          </span>
        </div>
      </header>

      <main style={{
        maxWidth: 1400, margin: "0 auto", padding: "24px",
        display: "grid", gridTemplateColumns: "380px 1fr", gap: 20,
      }}>

        {/* ── Left Sidebar ───────────────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Index Repo */}
          <section style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 16 }}>
            <SectionLabel num="01" label={t("section_index")} />
            <input
              placeholder={t("index_placeholder")}
              value={repoPath}
              onChange={e => setRepoPath(e.target.value)}
              disabled={isIndexing}
              style={{ marginBottom: 6 }}
            />
            <div style={{
              fontSize: 9, color: C.textMute, marginBottom: 8,
              fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.04em",
            }}>
              {t("index_hint")}
            </div>
            <button
              onClick={handleIndex}
              disabled={isIndexing || !repoPath.trim()}
              style={{ background: C.accent, color: "#fff", width: "100%" }}
            >
              {isIndexing ? t("index_button_loading") : t("index_button")}
            </button>

            {isIndexing && indexLog.length > 0 && (
              <div style={{
                marginTop: 12, background: C.bg3,
                border: `1px solid ${C.border}`, borderRadius: 5,
                padding: 10, maxHeight: 160, overflowY: "auto",
                fontFamily: "monospace", fontSize: 10,
              }}>
                {indexLog.slice(-10).map((evt, i) => (
                  <div key={i} style={{ color: C.textDim, marginBottom: 3, animation: "slideIn 0.3s" }}>
                    <span style={{ color: C.accent }}>›</span> {evt.data?.message || evt.type}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Repos list */}
          <section style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 16 }}>
            <SectionLabel num="02" label={t("section_repos")} />
            {repos.length === 0 ? (
              <div style={{ color: C.textFaint, fontSize: 12, padding: "16px 0", textAlign: "center" }}>
                {t("no_repos")}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {repos.map(r => (
                  <div
                    key={r.id}
                    onClick={() => setActiveRepo(r.id)}
                    style={{
                      padding: "10px 12px",
                      background: activeRepo === r.id ? `${C.accent}10` : C.bg3,
                      border: `1px solid ${activeRepo === r.id ? C.accent : C.border}`,
                      borderRadius: 5, cursor: "pointer", transition: "all 0.15s",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: C.text, fontFamily: "monospace" }}>
                        {r.path.split(/[/\\]/).pop()}
                      </div>
                      {activeRepo === r.id && <Pill color={C.accent}>{t("active")}</Pill>}
                    </div>
                    <div style={{ fontSize: 10, color: C.textMute, fontFamily: "monospace" }}>
                      {r.code_files} {t("files")} · {r.graph?.symbols_count || 0} {t("symbols")}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Project Profile */}
          {activeRepoMeta?.profile && (
            <section style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 16 }}>
              <SectionLabel num="03" label={t("section_profile")} />
              <div style={{ fontSize: 12, lineHeight: 1.6, color: C.textDim }}>
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 9, color: C.textMute, letterSpacing: "0.1em", marginBottom: 3 }}>{t("purpose")}</div>
                  <div style={{ fontSize: 11 }}>{activeRepoMeta.profile.purpose || "—"}</div>
                </div>
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 9, color: C.textMute, letterSpacing: "0.1em", marginBottom: 3 }}>{t("architecture")}</div>
                  <div style={{ fontFamily: "monospace", color: C.text, fontSize: 11 }}>
                    {activeRepoMeta.profile.architecture || "—"}
                  </div>
                </div>
                {activeRepoMeta.profile.frameworks?.length > 0 && (
                  <div style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 9, color: C.textMute, letterSpacing: "0.1em", marginBottom: 5 }}>{t("frameworks")}</div>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {activeRepoMeta.profile.frameworks.map(f => (
                        <Pill key={f} color={C.blue}>{f}</Pill>
                      ))}
                    </div>
                  </div>
                )}
                {activeRepoMeta.profile.notable_patterns?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 9, color: C.textMute, letterSpacing: "0.1em", marginBottom: 5 }}>{t("patterns")}</div>
                    <ul style={{ paddingLeft: 14, margin: 0 }}>
                      {activeRepoMeta.profile.notable_patterns.slice(0, 3).map((p, i) => (
                        <li key={i} style={{ fontSize: 11, marginBottom: 2 }}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>

        {/* ── Main Content ───────────────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Knowledge Graph 3D */}
          {activeGraph && activeGraph.nodes && activeGraph.nodes.length > 0 && (
            <section style={{
              background: C.bg2,
              border: `1px solid ${C.border}`,
              borderRadius: 8, padding: 0, overflow: "hidden",
            }}>
              <div style={{ padding: "12px 16px 8px" }}>
                <SectionLabel num="04" label={t("section_graph")} icon={highlightFiles.length > 0 ? t("files_highlighted", {n: highlightFiles.length}) : null} />
              </div>
              <GraphViz3D
                graph={activeGraph}
                highlightFiles={highlightFiles}
                height={360}
                onNodeClick={(node) => {
                  console.log("Clicked node:", node);
                }}
              />
            </section>
          )}

          {/* Diff input */}
          <section style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 18 }}>
            <SectionLabel num="05" label={t("section_diff")} />
            <textarea
              placeholder={t("diff_placeholder")}
              value={diff}
              onChange={e => setDiff(e.target.value)}
              rows={8}
              style={{ resize: "vertical", minHeight: 140 }}
              disabled={isReviewing}
            />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10 }}>
              <span style={{ fontSize: 10, color: C.textFaint, fontFamily: "monospace" }}>
                {t("diff_chars_lines", { chars: diff.length, lines: diff.split("\n").length })}
              </span>
              <button
                onClick={handleReview}
                disabled={isReviewing || !activeRepo || !diff.trim()}
                style={{ background: C.accent, color: "#fff" }}
              >
                {isReviewing ? t("review_button_loading") : t("review_button")}
              </button>
            </div>
          </section>

          {/* Pipeline Visualizer */}
          {(isReviewing || reviewResult || Object.keys(stageStates).length > 0) && (
            <section style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 18 }}>
              <SectionLabel num="06" label={t("section_pipeline")} />
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {PIPELINE_STAGES.map(stage => (
                  <StageNode
                    key={stage.id}
                    stage={stage}
                    status={stageStates[stage.id] || "pending"}
                    elapsed={stageData[stage.id]?._elapsed}
                    data={stageData[stage.id]}
                    t={t}
                  />
                ))}
              </div>
              {reviewResult?.timings && (
                <div style={{
                  marginTop: 12, paddingTop: 10,
                  borderTop: `1px solid ${C.border}`,
                  display: "flex", justifyContent: "space-between",
                }}>
                  <span style={{ fontSize: 10, color: C.textMute, fontFamily: "monospace" }}>
                    {t("total_time")}
                  </span>
                  <span style={{ fontSize: 11, color: C.accent, fontFamily: "monospace", fontWeight: 700 }}>
                    {Object.values(reviewResult.timings).reduce((a, b) => a + b, 0).toFixed(2)}s
                  </span>
                </div>
              )}
            </section>
          )}

          {/* Result */}
          {reviewResult?.report && (
            <section style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <SectionLabel num="07" label={t("section_result")} noMargin />
                <ExportMenu
                  reviewResult={reviewResult}
                  repoMeta={activeRepoMeta}
                  lang={lang}
                  t={t}
                  accent={C.accent}
                />
              </div>

              <div style={{
                background: reviewResult.report.approved ? `${C.green}10` : `${C.red}10`,
                border: `1px solid ${reviewResult.report.approved ? C.green : C.red}40`,
                borderRadius: 6, padding: "14px 16px", marginBottom: 14,
                display: "flex", gap: 14, alignItems: "flex-start",
              }}>
                <div style={{
                  fontSize: 22, fontWeight: 700, lineHeight: 1,
                  color: reviewResult.report.approved ? C.green : C.red,
                }}>
                  {reviewResult.report.approved ? "✓" : "✕"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: 10, letterSpacing: "0.1em",
                    fontWeight: 700, marginBottom: 6,
                    color: reviewResult.report.approved ? C.green : C.red,
                  }}>
                    {reviewResult.report.approved ? t("approved") : t("changes_required")}
                  </div>
                  <div style={{ fontSize: 13, color: C.textDim, lineHeight: 1.6 }}>
                    {reviewResult.report.overall_verdict}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
                <StatBox label={t("stat_critical")} value={reviewResult.report.stats.critical} color={C.red} />
                <StatBox label={t("stat_major")} value={reviewResult.report.stats.major} color={C.orange} />
                <StatBox label={t("stat_minor")} value={reviewResult.report.stats.minor} color={C.yellow} />
                <StatBox label={t("stat_suggest")} value={reviewResult.report.stats.suggestion} color={C.green} />
                <StatBox label={t("stat_filtered")} value={reviewResult.report.stats.filtered_by_critic || 0} color={C.textMute} />
                <StatBox label={t("stat_total")} value={reviewResult.report.stats.total} color={C.text} />
              </div>

              {issues.length > 0 ? (
                <div>
                  <div style={{ fontSize: 10, color: C.textMute, marginBottom: 10, letterSpacing: "0.1em", fontWeight: 700 }}>
                    {t("issues_validated")} ({issues.length})
                  </div>
                  {issues.map((issue, i) => <IssueCard key={i} issue={issue} t={t} />)}
                </div>
              ) : (
                <div style={{ color: C.textMute, fontSize: 13, textAlign: "center", padding: 24 }}>
                  {t("no_issues")}
                </div>
              )}
            </section>
          )}

          {error && (
            <div style={{
              background: `${C.red}10`, border: `1px solid ${C.red}30`,
              borderRadius: 6, padding: 14, color: C.red,
              fontSize: 12, fontFamily: "monospace",
            }}>
              ✕ {error}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
