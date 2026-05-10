"""
Reviewer v2 - few-shot prompting, structured JSON output, adversarial critic with scoring.
"""
from agents.llm_client import get_llm
from typing import Optional
import json
import re


# ── Robust JSON parsing ─────────────────────────────────────────────────

def _extract_json(text: str):
    """Extrai JSON de uma resposta LLM (mesmo se vier dentro de markdown)."""
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()

    # Tenta parse direto
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Tenta achar primeiro array ou objeto
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        if start == -1:
            continue
        # Procura o final balanceado
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        break
    return None


def _validate_issues(issues) -> list[dict]:
    """Valida e normaliza estrutura dos issues."""
    if not isinstance(issues, list):
        return []

    valid = []
    for item in issues:
        if not isinstance(item, dict):
            continue

        normalized = {
            "severity": str(item.get("severity", "minor")).lower(),
            "category": str(item.get("category", "other")),
            "file": str(item.get("file", "unknown")),
            "line": item.get("line"),
            "description": str(item.get("description", "")).strip(),
            "justification": str(item.get("justification", "")).strip(),
            "suggestion": str(item.get("suggestion", "")).strip(),
        }

        if normalized["severity"] not in ("critical", "major", "minor", "suggestion"):
            normalized["severity"] = "minor"

        if not normalized["description"]:
            continue

        valid.append(normalized)

    return valid


# ── Reviewer ─────────────────────────────────────────────────────────────

REVIEWER_FEW_SHOT_PT = """
EXEMPLO DE BOA REVIEW (com justificativa específica ao projeto):

DIFF:
+ def delete_user(self, uid):
+     u = self.db.query(User).filter(User.id == uid).first()
+     self.db.delete(u)
+     self.db.commit()

CONTEXTO DO PROJETO: Outras operações de delete em src/services/ usam padrão:
  - validação prévia (raise UserNotFound)
  - logging.info de auditoria
  - typing hints completos

GOOD ISSUE:
{
  "severity": "major",
  "category": "consistency",
  "file": "src/user_service.py",
  "line": 49,
  "description": "delete_user não valida existência do usuário e não tem logging",
  "justification": "Outros métodos de delete no projeto (visto em src/services/) seguem padrão: validar antes (raise UserNotFound), logar a ação para auditoria, e usar type hints. Este método quebra os 3 padrões.",
  "suggestion": "Adicionar: type hint `uid: int`, validação `if u is None: raise UserNotFound(uid)`, e `logger.info(f'User {uid} deleted by ...')'`"
}

EXEMPLO DE BAD ISSUE (genérico, deve ser evitado):
{
  "severity": "minor",
  "description": "O nome 'uid' não é descritivo",
  "justification": "Nomes descritivos são melhores."
}
↑ FALHA porque a justificativa é genérica, não cita o contexto do projeto.
"""

REVIEWER_FEW_SHOT_EN = """
EXAMPLE OF A GOOD REVIEW (project-specific justification):

DIFF:
+ def delete_user(self, uid):
+     u = self.db.query(User).filter(User.id == uid).first()
+     self.db.delete(u)
+     self.db.commit()

PROJECT CONTEXT: Other delete operations in src/services/ follow this pattern:
  - prior validation (raise UserNotFound)
  - logging.info for auditing
  - complete type hints

GOOD ISSUE:
{
  "severity": "major",
  "category": "consistency",
  "file": "src/user_service.py",
  "line": 49,
  "description": "delete_user does not validate user existence and lacks logging",
  "justification": "Other delete methods in this project (seen in src/services/) follow a clear pattern: validate before deletion (raise UserNotFound), log the action for audit, and use type hints. This method breaks all 3 conventions.",
  "suggestion": "Add: type hint `uid: int`, validation `if u is None: raise UserNotFound(uid)`, and `logger.info(f'User {uid} deleted by ...')'`"
}

BAD ISSUE EXAMPLE (generic, must be avoided):
{
  "severity": "minor",
  "description": "Variable name 'uid' is not descriptive",
  "justification": "Descriptive names are better."
}
↑ FAILS because the justification is generic, not citing project-specific context.
"""


def _build_reviewer_prompt(diff: str, context_synthesis: str, project_profile: dict, lang: str) -> str:
    if lang == "pt":
        profile_text = (
            f"PROPÓSITO: {project_profile.get('purpose', 'N/A')}\n"
            f"ARQUITETURA: {project_profile.get('architecture', 'unknown')}\n"
            f"LINGUAGENS: {', '.join(project_profile.get('main_languages', []))}\n"
            f"FRAMEWORKS: {', '.join(project_profile.get('frameworks', []))}\n"
            f"CONVENÇÕES: {project_profile.get('naming_conventions', 'N/A')}\n"
            f"PADRÕES NOTÁVEIS: {project_profile.get('notable_patterns', [])}\n"
        )
        return f"""Você é um code reviewer sênior que conhece profundamente este projeto.

{profile_text}

CONTEXTO RELEVANTE (síntese do RAG):
{context_synthesis}

DIFF A REVISAR:
{diff}

{REVIEWER_FEW_SHOT_PT}

REGRAS CRÍTICAS:
1. CADA issue DEVE ter justificativa específica ao projeto, citando padrões/arquivos/convenções concretas
2. NÃO inclua issues genéricos (ex: "use nomes melhores")
3. Categorize: bug | security | performance | architecture | consistency | naming | test | error_handling
4. Severidade: critical (quebra produção) | major (problema sério) | minor (inconveniente) | suggestion (melhoria)
5. Se o diff está bom, retorne array vazio []
6. Escreva todos os textos (description, justification, suggestion) em PORTUGUÊS

Retorne APENAS um array JSON com a estrutura mostrada acima. Sem markdown, sem comentários."""

    # English
    profile_text = (
        f"PURPOSE: {project_profile.get('purpose', 'N/A')}\n"
        f"ARCHITECTURE: {project_profile.get('architecture', 'unknown')}\n"
        f"LANGUAGES: {', '.join(project_profile.get('main_languages', []))}\n"
        f"FRAMEWORKS: {', '.join(project_profile.get('frameworks', []))}\n"
        f"CONVENTIONS: {project_profile.get('naming_conventions', 'N/A')}\n"
        f"NOTABLE PATTERNS: {project_profile.get('notable_patterns', [])}\n"
    )
    return f"""You are a senior code reviewer who deeply knows this project.

{profile_text}

RELEVANT CONTEXT (RAG synthesis):
{context_synthesis}

DIFF TO REVIEW:
{diff}

{REVIEWER_FEW_SHOT_EN}

CRITICAL RULES:
1. EACH issue MUST have a project-specific justification, citing concrete patterns/files/conventions
2. DO NOT include generic issues (e.g., "use better names")
3. Categorize: bug | security | performance | architecture | consistency | naming | test | error_handling
4. Severity: critical (breaks production) | major (serious issue) | minor (inconvenience) | suggestion (improvement)
5. If the diff is fine, return an empty array []
6. Write all text (description, justification, suggestion) in ENGLISH

Return ONLY a JSON array with the structure shown above. No markdown, no comments."""


def run_reviewer(
    diff: str,
    context_synthesis: str,
    project_profile: dict,
    affected_symbols: Optional[list] = None,
    lang: str = "en",
) -> list[dict]:
    """Executa o reviewer com few-shot e structured output."""
    llm = get_llm(temperature=0.15)
    prompt = _build_reviewer_prompt(diff, context_synthesis, project_profile, lang)
    response = llm.invoke(prompt)
    parsed = _extract_json(response.content)
    issues = _validate_issues(parsed) if parsed else []
    return issues


def run_critic(
    issues: list[dict],
    diff: str,
    context_synthesis: str,
    project_profile: dict,
    lang: str = "en",
) -> dict:
    """
    Critic estruturado: pra cada issue, avalia e retorna decisão + razão.
    Retorna {validated: [...], rejected: [...]}
    """
    if not issues:
        return {"validated": [], "rejected": []}

    llm = get_llm(temperature=0.3)

    issues_with_ids = [{**iss, "_id": i} for i, iss in enumerate(issues)]

    if lang == "pt":
        prompt = f"""Você é o ADVOGADO DO DIABO. Sua função é eliminar code review issues fracos.

CONTEXTO DO PROJETO:
- Arquitetura: {project_profile.get('architecture', 'unknown')}
- Padrões: {project_profile.get('notable_patterns', [])}

CONTEXTO DO PR:
{context_synthesis[:1500]}

DIFF:
{diff[:2500]}

ISSUES PROPOSTOS PELO REVIEWER:
{json.dumps(issues_with_ids, indent=2, ensure_ascii=False)}

Para CADA issue, decida:
- "keep" se a justificativa cita padrões/decisões específicas do projeto
- "reject" se for genérico ou falso positivo

Retorne JSON:
{{
  "evaluations": [
    {{"_id": 0, "decision": "keep|reject", "reason": "razão curta", "confidence": 0.0-1.0}},
    ...
  ]
}}

Critérios para REJECT:
- Justificativa genérica (não cita projeto específico)
- O "problema" não existe de fato no diff
- Severidade exagerada (major/critical sem motivo real)

Apenas JSON, sem markdown."""
    else:
        prompt = f"""You are the DEVIL'S ADVOCATE. Your job is to eliminate weak code review issues.

PROJECT CONTEXT:
- Architecture: {project_profile.get('architecture', 'unknown')}
- Patterns: {project_profile.get('notable_patterns', [])}

PR CONTEXT:
{context_synthesis[:1500]}

DIFF:
{diff[:2500]}

ISSUES PROPOSED BY THE REVIEWER:
{json.dumps(issues_with_ids, indent=2, ensure_ascii=False)}

For EACH issue, decide:
- "keep" if the justification cites project-specific patterns/decisions
- "reject" if generic or false positive

Return JSON:
{{
  "evaluations": [
    {{"_id": 0, "decision": "keep|reject", "reason": "short reason", "confidence": 0.0-1.0}},
    ...
  ]
}}

REJECT criteria:
- Generic justification (does not cite the specific project)
- The "issue" does not actually exist in the diff
- Exaggerated severity (major/critical without real reason)

JSON only, no markdown."""

    response = llm.invoke(prompt)
    parsed = _extract_json(response.content)

    if not parsed or "evaluations" not in parsed:
        return {"validated": issues, "rejected": []}

    keep_ids = set()
    rejection_reasons = {}
    for ev in parsed.get("evaluations", []):
        try:
            iid = int(ev["_id"])
            decision = ev.get("decision", "keep").lower()
            if decision == "keep":
                keep_ids.add(iid)
            else:
                rejection_reasons[iid] = ev.get("reason", "rejected by critic")
        except (KeyError, ValueError, TypeError):
            continue

    validated = [iss for i, iss in enumerate(issues) if i in keep_ids]
    rejected = [
        {**iss, "_rejection_reason": rejection_reasons.get(i, "")}
        for i, iss in enumerate(issues) if i not in keep_ids
    ]

    return {"validated": validated, "rejected": rejected}


# ── Reporter ──────────────────────────────────────────────────────────────

def run_reporter(
    validated_issues: list[dict],
    rejected_issues: list[dict],
    diff_stats: dict,
    project_profile: dict,
    lang: str = "en",
) -> dict:
    """Gera relatório final com veredicto."""
    critical = [i for i in validated_issues if i.get("severity") == "critical"]
    major = [i for i in validated_issues if i.get("severity") == "major"]
    minor = [i for i in validated_issues if i.get("severity") == "minor"]
    suggestion = [i for i in validated_issues if i.get("severity") == "suggestion"]

    approved = len(critical) == 0 and len(major) == 0

    llm = get_llm(temperature=0.2)

    if lang == "pt":
        summary_prompt = f"""Gere um veredicto executivo de 2-3 frases para este code review.

ESTATÍSTICAS:
- Critical: {len(critical)}
- Major: {len(major)}
- Minor: {len(minor)}
- Suggestions: {len(suggestion)}
- Issues filtrados pelo critic: {len(rejected_issues)}
- Aprovado: {approved}

DIFF: {diff_stats.get('additions', 0)} adições, {diff_stats.get('deletions', 0)} remoções em {len(diff_stats.get('files', []))} arquivo(s)

TOP ISSUES (por severidade):
{json.dumps([{
    "severity": i["severity"],
    "description": i["description"][:100]
} for i in (critical + major)[:3]], indent=2, ensure_ascii=False)}

Escreva um veredicto profissional e específico ao projeto. Direto ao ponto. Em PORTUGUÊS."""
    else:
        summary_prompt = f"""Generate a 2-3 sentence executive verdict for this code review.

STATISTICS:
- Critical: {len(critical)}
- Major: {len(major)}
- Minor: {len(minor)}
- Suggestions: {len(suggestion)}
- Issues filtered by critic: {len(rejected_issues)}
- Approved: {approved}

DIFF: {diff_stats.get('additions', 0)} additions, {diff_stats.get('deletions', 0)} deletions across {len(diff_stats.get('files', []))} file(s)

TOP ISSUES (by severity):
{json.dumps([{
    "severity": i["severity"],
    "description": i["description"][:100]
} for i in (critical + major)[:3]], indent=2, ensure_ascii=False)}

Write a professional, project-specific verdict. Concise and direct. In ENGLISH."""

    response = llm.invoke(summary_prompt)
    verdict = response.content.strip()

    return {
        "issues": validated_issues,
        "rejected_issues": rejected_issues,
        "overall_verdict": verdict,
        "approved": approved,
        "stats": {
            "critical": len(critical),
            "major": len(major),
            "minor": len(minor),
            "suggestion": len(suggestion),
            "total": len(validated_issues),
            "filtered_by_critic": len(rejected_issues),
        }
    }
