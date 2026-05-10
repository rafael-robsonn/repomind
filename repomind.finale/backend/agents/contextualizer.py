"""
Contextualizer v2 - structured diff analysis + symbol-aware retrieval.
"""
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma
from agents.llm_client import get_llm
from agents.diff_parser import parse_diff, affected_symbols, ParsedDiff
import json


def _llm_extract_queries(diff: str, project_profile: dict, llm) -> list[str]:
    """LLM gera queries de busca específicas para o contexto."""
    profile_summary = (
        f"Stack: {project_profile.get('main_languages', [])}, "
        f"Frameworks: {project_profile.get('frameworks', [])}, "
        f"Arch: {project_profile.get('architecture', 'unknown')}"
    )

    prompt = f"""Você está revisando um PR neste projeto: {profile_summary}

Padrões conhecidos: {project_profile.get('notable_patterns', [])}
Convenções: {project_profile.get('naming_conventions', '')}

DIFF:
{diff[:2500]}

Liste 4-6 queries de busca curtas para encontrar contexto relevante no codebase.
Foque em:
1. Símbolos/funções similares já existentes (pra detectar inconsistência)
2. Arquivos que provavelmente importam o que foi modificado
3. Padrões arquiteturais que podem estar sendo violados
4. Testes relacionados

Responda APENAS com as queries, uma por linha, sem numeração."""

    response = llm.invoke(prompt)
    queries = [q.strip().lstrip("0123456789.- ") for q in response.content.strip().split("\n")]
    return [q for q in queries if q and len(q) > 3][:6]


def contextualize_diff(diff: str, vectorstore: Chroma, project_profile: dict) -> dict:
    """
    Análise estruturada:
    1. Parse do diff
    2. Identifica símbolos afetados
    3. Busca contexto de múltiplas queries
    4. Sintetiza relevância via LLM
    """
    llm = get_llm(temperature=0.1)

    parsed = parse_diff(diff)
    affected = affected_symbols(parsed)

    file_contexts = []
    for file in parsed.files_changed()[:5]:
        results = vectorstore.similarity_search(file, k=2)
        for doc in results:
            file_contexts.append(doc)

    symbol_contexts = []
    for sym_info in affected[:5]:
        query = f"{sym_info['kind']} {sym_info['symbol']}"
        results = vectorstore.similarity_search(query, k=2)
        for doc in results:
            symbol_contexts.append(doc)

    queries = _llm_extract_queries(diff, project_profile, llm)
    semantic_contexts = []
    for q in queries:
        results = vectorstore.similarity_search(q, k=3)
        for doc in results:
            semantic_contexts.append(doc)

    seen = set()
    all_contexts = []
    for doc in file_contexts + symbol_contexts + semantic_contexts:
        key = doc.metadata.get("file", "") + str(doc.page_content)[:100]
        if key not in seen:
            seen.add(key)
            all_contexts.append(doc)

    context_text_parts = []
    total_chars = 0
    for doc in all_contexts[:15]:
        snippet = f"\n[FILE: {doc.metadata.get('file', '?')}]\n{doc.page_content[:600]}"
        if total_chars + len(snippet) > 6000:
            break
        context_text_parts.append(snippet)
        total_chars += len(snippet)

    context_text = "\n".join(context_text_parts)

    synthesis_prompt = f"""Sintetize o contexto relevante para revisar este PR.

PROJETO:
- Propósito: {project_profile.get('purpose', 'N/A')}
- Arquitetura: {project_profile.get('architecture', 'unknown')}
- Padrões notáveis: {project_profile.get('notable_patterns', [])}
- Convenções: {project_profile.get('naming_conventions', 'N/A')}

DIFF SUMMARY:
{parsed.to_summary()}

SÍMBOLOS AFETADOS:
{json.dumps(affected, indent=2) if affected else 'Nenhum identificado'}

CONTEXTO RECUPERADO DO REPO:
{context_text}

Produza uma síntese OBJETIVA cobrindo:
1. Padrões do projeto que se aplicam a este diff
2. Funções/classes similares que já existem (consistência?)
3. Possíveis impactos em outros módulos
4. Convenções específicas que o reviewer deve verificar

Seja específico ao projeto, não genérico. Máximo 400 palavras."""

    synthesis_response = llm.invoke(synthesis_prompt)

    return {
        "parsed": {
            "files": parsed.files_changed(),
            "hunks_count": len(parsed.hunks),
            "additions": parsed.additions,
            "deletions": parsed.deletions,
        },
        "affected_symbols": affected,
        "queries_used": queries,
        "context_files": list(dict.fromkeys(
            d.metadata.get("file", "?").replace("\\", "/") for d in all_contexts[:15]
        )),
        "synthesis": synthesis_response.content,
    }
