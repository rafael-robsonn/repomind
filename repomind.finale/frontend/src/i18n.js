// ── i18n - English / Portuguese ─────────────────────────────────────────

export const TRANSLATIONS = {
  en: {
    // Header
    tagline: "CONTEXT-AWARE CODE REVIEW · LANGGRAPH · TREE-SITTER",
    online: "ONLINE",

    // Sections
    section_index: "INDEX REPO",
    section_repos: "REPOS",
    section_profile: "PROFILE",
    section_graph: "KNOWLEDGE GRAPH 3D",
    section_diff: "REVIEW DIFF",
    section_pipeline: "PIPELINE EXECUTION",
    section_result: "RESULT",

    // Index
    index_placeholder: "C:\\projects\\repo  or  https://github.com/user/repo",
    index_hint: "local path OR github url (will be cloned automatically)",
    index_button: "INDEX REPOSITORY",
    index_button_loading: "INDEXING...",
    no_repos: "No repository indexed yet",
    active: "ACTIVE",
    files: "files",
    symbols: "symbols",

    // Profile
    purpose: "PURPOSE",
    architecture: "ARCHITECTURE",
    frameworks: "FRAMEWORKS",
    patterns: "PATTERNS",

    // Graph
    legend: "LEGEND",
    knowledge_graph: "KNOWLEDGE GRAPH",
    nodes: "nodes",
    edges: "edges",
    of_total: "of {n} files total",
    drag_scroll_click: "DRAG · SCROLL · CLICK",
    files_highlighted: "{n} files highlighted",

    // Diff
    diff_placeholder: 'Paste "git diff" output here...',
    diff_chars_lines: "{chars} chars · {lines} lines",
    review_button: "EXECUTE PIPELINE →",
    review_button_loading: "ANALYZING...",
    total_time: "TOTAL TIME",

    // Pipeline stages
    stage_parse_label: "Parse Diff",
    stage_parse_desc: "Extracts files, hunks, symbols",
    stage_contextualize_label: "Contextualize",
    stage_contextualize_desc: "Retrieves project context",
    stage_review_label: "Review",
    stage_review_desc: "Reviewer agent with few-shot",
    stage_critic_label: "Critic",
    stage_critic_desc: "Adversarial filter",
    stage_report_label: "Report",
    stage_report_desc: "Final verdict",

    stage_context_files: "{n} context files retrieved",
    stage_queries: "queries",
    stage_raw_issues: "{n} issues raised",
    stage_validated: "{n} validated",
    stage_filtered: "{n} filtered",

    // Result
    approved: "APPROVED",
    changes_required: "CHANGES REQUIRED",
    no_issues: "No issues found.",
    issues_validated: "VALIDATED ISSUES",
    severity_critical: "CRITICAL",
    severity_major: "MAJOR",
    severity_minor: "MINOR",
    severity_suggestion: "SUGGEST",
    stat_critical: "CRITICAL",
    stat_major: "MAJOR",
    stat_minor: "MINOR",
    stat_suggest: "SUGGEST",
    stat_filtered: "FILTERED",
    stat_total: "TOTAL",
    justification: "JUSTIFICATION",
    suggestion: "SUGGESTION",

    // Export
    export: "EXPORT",
    export_md: "Markdown",
    export_pdf: "PDF",
    exporting: "Exporting...",
  },

  pt: {
    tagline: "CODE REVIEW CONTEXTUAL · LANGGRAPH · TREE-SITTER",
    online: "ONLINE",

    section_index: "INDEXAR REPO",
    section_repos: "REPOS",
    section_profile: "PROFILE",
    section_graph: "KNOWLEDGE GRAPH 3D",
    section_diff: "REVISAR DIFF",
    section_pipeline: "PIPELINE EXECUTION",
    section_result: "RESULTADO",

    index_placeholder: "C:\\projetos\\repo  ou  https://github.com/user/repo",
    index_hint: "caminho local OU url github (será clonado automaticamente)",
    index_button: "INDEXAR REPOSITÓRIO",
    index_button_loading: "INDEXANDO...",
    no_repos: "Nenhum repositório indexado",
    active: "ATIVO",
    files: "arquivos",
    symbols: "símbolos",

    purpose: "PROPÓSITO",
    architecture: "ARQUITETURA",
    frameworks: "FRAMEWORKS",
    patterns: "PADRÕES",

    legend: "LEGENDA",
    knowledge_graph: "KNOWLEDGE GRAPH",
    nodes: "nodes",
    edges: "edges",
    of_total: "de {n} arquivos no total",
    drag_scroll_click: "ARRASTAR · SCROLL · CLICK",
    files_highlighted: "{n} arquivos destacados",

    diff_placeholder: 'Cole o output de "git diff" aqui...',
    diff_chars_lines: "{chars} chars · {lines} linhas",
    review_button: "EXECUTAR PIPELINE →",
    review_button_loading: "ANALISANDO...",
    total_time: "TEMPO TOTAL",

    stage_parse_label: "Parse Diff",
    stage_parse_desc: "Extrai files, hunks, símbolos",
    stage_contextualize_label: "Contextualize",
    stage_contextualize_desc: "Recupera contexto do projeto",
    stage_review_label: "Review",
    stage_review_desc: "Reviewer agent com few-shot",
    stage_critic_label: "Critic",
    stage_critic_desc: "Adversarial filter",
    stage_report_label: "Report",
    stage_report_desc: "Veredicto final",

    stage_context_files: "{n} arquivos de contexto recuperados",
    stage_queries: "queries",
    stage_raw_issues: "{n} issues levantados",
    stage_validated: "{n} validados",
    stage_filtered: "{n} filtrados",

    approved: "APROVADO",
    changes_required: "MUDANÇAS NECESSÁRIAS",
    no_issues: "Nenhum issue encontrado.",
    issues_validated: "ISSUES VALIDADOS",
    severity_critical: "CRITICAL",
    severity_major: "MAJOR",
    severity_minor: "MINOR",
    severity_suggestion: "SUGEST",
    stat_critical: "CRITICAL",
    stat_major: "MAJOR",
    stat_minor: "MINOR",
    stat_suggest: "SUGEST",
    stat_filtered: "FILTRADOS",
    stat_total: "TOTAL",
    justification: "JUSTIFICATIVA",
    suggestion: "SUGESTÃO",

    export: "EXPORTAR",
    export_md: "Markdown",
    export_pdf: "PDF",
    exporting: "Exportando...",
  },
};


export function getInitialLang() {
  try {
    const saved = localStorage.getItem("repomind:lang");
    if (saved === "en" || saved === "pt") return saved;
  } catch {}
  // Default: navigator language
  return (navigator.language || "en").startsWith("pt") ? "pt" : "en";
}


export function saveLang(lang) {
  try {
    localStorage.setItem("repomind:lang", lang);
  } catch {}
}


export function makeT(lang) {
  const dict = TRANSLATIONS[lang] || TRANSLATIONS.en;
  return (key, vars) => {
    let s = dict[key] || TRANSLATIONS.en[key] || key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.replace(`{${k}}`, v);
      }
    }
    return s;
  };
}
