"""
Repository indexer with AST analysis, knowledge graph, and persistent cache.
"""
import os
import json
import hashlib
from pathlib import Path
from typing import Callable, Optional
import networkx as nx
import diskcache

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

try:
    from langchain_core.documents import Document
except ImportError:
    from langchain.schema import Document

from agents.llm_client import get_llm
from agents.code_analyzer import analyze_file, detect_project_type, FileAnalysis
from dotenv import load_dotenv

load_dotenv()

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".cpp", ".c", ".h", ".cs", ".rb", ".php",
    ".md", ".txt", ".yaml", ".yml", ".toml", ".json"
}

CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".rb"}

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache",
    "dist", "build", ".next", "target", "vendor", ".turbo", "coverage",
    ".idea", ".vscode", "out", "tmp", ".cache"
}

CACHE_DIR = "./.repomind_cache"


# ── Singletons ──────────────────────────────────────────────────────────

_embeddings = None
_cache = None


def _detect_device():
    """Auto-detecta CUDA/MPS/CPU. Logs o que escolheu."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            print(f"[Embeddings] CUDA disponível: {name}")
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            print(f"[Embeddings] MPS (Apple Silicon) disponível")
            return "mps"
    except Exception as e:
        print(f"[Embeddings] Erro detectando GPU: {e}")
    print(f"[Embeddings] Usando CPU (lento para repos grandes)")
    return "cpu"


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        device = os.getenv("REPOMIND_EMBED_DEVICE") or _detect_device()
        batch_size = 64 if device == "cuda" else 8
        _embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-en-v1.5",
            model_kwargs={"device": device},
            encode_kwargs={
                "normalize_embeddings": True,
                "batch_size": batch_size,
            },
            show_progress=True,
        )
    return _embeddings


def get_cache():
    global _cache
    if _cache is None:
        os.makedirs(CACHE_DIR, exist_ok=True)
        _cache = diskcache.Cache(CACHE_DIR)
    return _cache


# ── File loading ────────────────────────────────────────────────────────

LOW_PRIORITY_DIRS = {
    "tests", "test", "__tests__", "spec", "specs",
    "docs", "doc", "documentation", "examples", "example", "samples",
    "fixtures", "mocks", "__mocks__", "vendor", "third_party",
    "scripts", "tools", "benchmark", "benchmarks",
}


def _file_priority(fp: Path, root: Path) -> int:
    """
    Score de prioridade: 0=máxima (código fonte principal), 3=mínima (docs/tests).
    Usado pra cortar repos gigantes mantendo o que importa pra review.
    """
    parts = fp.relative_to(root).parts
    parts_lower = {p.lower() for p in parts}

    # Docs/configs sempre baixa prioridade
    if fp.suffix in {".md", ".txt", ".json", ".yaml", ".yml", ".toml"}:
        return 3
    # Test
    if parts_lower & LOW_PRIORITY_DIRS:
        return 2
    # Filename sugere teste
    name = fp.name.lower()
    if name.startswith("test_") or name.endswith("_test.py") or ".test." in name or ".spec." in name:
        return 2
    # Código source principal
    if fp.suffix in CODE_EXTENSIONS:
        return 0
    return 1


def collect_files(repo_path: str, max_files: Optional[int] = None) -> list[Path]:
    root = Path(repo_path)
    if not root.exists():
        raise FileNotFoundError(f"Repo path não existe: {repo_path}")

    if max_files is None:
        max_files = int(os.getenv("REPOMIND_MAX_FILES", "400"))

    candidates = []
    for fp in root.rglob("*"):
        if not fp.is_file():
            continue
        if any(part in IGNORE_DIRS for part in fp.parts):
            continue
        if fp.suffix not in SUPPORTED_EXTENSIONS:
            continue
        try:
            if fp.stat().st_size > 500_000:
                continue
        except OSError:
            continue
        candidates.append(fp)

    if len(candidates) <= max_files:
        return candidates
    candidates.sort(key=lambda fp: (_file_priority(fp, root), -fp.stat().st_size))
    return candidates[:max_files]


def file_hash(filepath: Path) -> str:
    stat = filepath.stat()
    return hashlib.md5(f"{filepath}:{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()


# ── Knowledge Graph ─────────────────────────────────────────────────────

def build_knowledge_graph(analyses: list[FileAnalysis], repo_root: Path) -> nx.DiGraph:
    """
    Constrói grafo: arquivo -> arquivo (importa) e arquivo -> símbolo (define).
    """
    g = nx.DiGraph()

    for a in analyses:
        rel = str(Path(a.path).relative_to(repo_root))
        g.add_node(rel, type="file", language=a.language, loc=a.loc, symbols_count=len(a.symbols))
        for sym in a.symbols:
            sym_id = f"{rel}::{sym.parent}::{sym.name}" if sym.parent else f"{rel}::{sym.name}"
            g.add_node(sym_id, type="symbol", kind=sym.kind, line=sym.line, name=sym.name)
            g.add_edge(rel, sym_id, relation="defines")

    file_paths = {str(Path(a.path).relative_to(repo_root)) for a in analyses}
    for a in analyses:
        rel = str(Path(a.path).relative_to(repo_root))
        for imp in a.imports:
            if a.language == "python":
                m = imp.replace("from ", "").split("import")[0].strip()
                if m.startswith("."):
                    continue
                # busca arquivo correspondente
                possible = m.replace(".", "/") + ".py"
                for fp in file_paths:
                    if fp.endswith(possible):
                        g.add_edge(rel, fp, relation="imports")
                        break

    return g


def graph_summary(g: nx.DiGraph) -> dict:
    files = [n for n, d in g.nodes(data=True) if d.get("type") == "file"]
    symbols = [n for n, d in g.nodes(data=True) if d.get("type") == "symbol"]
    import_edges = [e for e in g.edges(data=True) if e[2].get("relation") == "imports"]

    # Most imported files (centrality)
    if files:
        sub = g.subgraph(files)
        centrality = sorted(
            [(n, sub.in_degree(n)) for n in sub.nodes()],
            key=lambda x: -x[1],
        )[:10]
    else:
        centrality = []

    return {
        "files_count": len(files),
        "symbols_count": len(symbols),
        "import_edges": len(import_edges),
        "central_files": centrality,
    }


def serialize_graph_for_viz(g: nx.DiGraph, max_nodes: int = 150) -> dict:
    """
    Serializa o grafo pra visualização 3D (Three.js).
    Normaliza paths pra forward slash pra compatibilidade Windows/Linux.
    """
    file_nodes = [(n, d) for n, d in g.nodes(data=True) if d.get("type") == "file"]

    # Pega os top N por (in_degree + out_degree + symbols_count)
    sub = g.subgraph([n for n, _ in file_nodes])
    scored = sorted(
        file_nodes,
        key=lambda nd: (
            sub.in_degree(nd[0]) * 3
            + sub.out_degree(nd[0])
            + nd[1].get("symbols_count", 0) * 0.3
        ),
        reverse=True,
    )[:max_nodes]

    selected_ids = {n for n, _ in scored}

    def norm(p):
        """Normaliza path pra forward slash."""
        return (p or "").replace("\\", "/")

    nodes = []
    for name, data in scored:
        nodes.append({
            "id": norm(name),
            "label": norm(name).split("/")[-1],
            "path": norm(name),
            "group": data.get("language", "unknown"),
            "loc": data.get("loc", 0),
            "symbols": data.get("symbols_count", 0),
            "in_degree": sub.in_degree(name),
            "out_degree": sub.out_degree(name),
        })

    edges = []
    for u, v, d in g.edges(data=True):
        if d.get("relation") != "imports":
            continue
        if u in selected_ids and v in selected_ids:
            edges.append({"source": norm(u), "target": norm(v)})

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_files": len(file_nodes),
            "total_edges": len([e for e in g.edges(data=True) if e[2].get("relation") == "imports"]),
            "showing_nodes": len(nodes),
            "showing_edges": len(edges),
        }
    }


# ── Project profile via LLM ──────────────────────────────────────────────

def build_project_profile(
    analyses: list[FileAnalysis],
    project_type: dict,
    graph_info: dict,
    repo_root: Path,
    llm,
) -> dict:
    """Sintetiza um profile rico do projeto via LLM."""

    # Coleta README
    readme_content = ""
    for fname in ["README.md", "README.rst", "README.txt", "readme.md"]:
        readme_path = repo_root / fname
        if readme_path.exists():
            readme_content = readme_path.read_text(encoding="utf-8", errors="ignore")[:3000]
            break

    # Top-level structure
    top_dirs = sorted({str(Path(a.path).relative_to(repo_root).parts[0])
                      for a in analyses if Path(a.path).relative_to(repo_root).parts})
    top_dirs = [d for d in top_dirs if not d.startswith(".")][:15]

    # Most central files (from graph)
    central = [f"{name} (imported by {count})" for name, count in graph_info["central_files"][:5]]

    # Sample of class/function names for pattern detection
    sample_symbols = []
    for a in analyses[:30]:
        for sym in a.symbols[:3]:
            if sym.kind in ("class", "function"):
                sample_symbols.append(f"{sym.kind} {sym.name}")
    sample_symbols = sample_symbols[:30]

    prompt = f"""Analise este repositório e produza um profile estruturado.

STACK DETECTADA: {", ".join(project_type.get("stack", []))}
FRAMEWORKS: {", ".join(project_type.get("frameworks", []))}

ESTRUTURA DE TOP-LEVEL:
{chr(10).join("- " + d for d in top_dirs)}

ARQUIVOS CENTRAIS (mais importados):
{chr(10).join("- " + c for c in central) if central else "(grafo de imports vazio)"}

SÍMBOLOS DE AMOSTRA:
{chr(10).join("- " + s for s in sample_symbols)}

ESTATÍSTICAS:
- {graph_info["files_count"]} arquivos de código
- {graph_info["symbols_count"]} símbolos (classes/funções)
- {graph_info["import_edges"]} relações de import internas

README (primeiras linhas):
{readme_content[:1500]}

Produza um JSON com EXATAMENTE estas chaves:
- "purpose": propósito do projeto em 1-2 frases
- "architecture": padrão arquitetural identificado (ex: "MVC", "layered", "monorepo", "modular monolith")
- "main_languages": lista de linguagens principais
- "frameworks": lista de frameworks/libs principais
- "naming_conventions": convenções observadas (ex: "snake_case para funções, PascalCase para classes")
- "code_organization": como o código está organizado em diretórios
- "notable_patterns": padrões de design notáveis observados (ex: "factory pattern em src/factories", "service layer")
- "potential_concerns": áreas que parecem frágeis ou inconsistentes (se houver)

Responda APENAS o JSON puro, sem markdown."""

    response = llm.invoke(prompt)
    text = response.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        profile = json.loads(text)
    except Exception as e:
        profile = {
            "purpose": "Não foi possível extrair propósito.",
            "architecture": "unknown",
            "main_languages": project_type.get("stack", []),
            "frameworks": project_type.get("frameworks", []),
            "naming_conventions": "",
            "code_organization": "",
            "notable_patterns": [],
            "potential_concerns": [],
            "_parse_error": str(e),
        }

    return profile


# ── Indexação principal com progress callbacks ──────────────────────────

ProgressCb = Callable[[str, dict], None]


def index_repository(
    repo_path: str,
    collection_name: Optional[str] = None,
    on_progress: Optional[ProgressCb] = None,
) -> dict:
    """
    Indexa repositório com:
    - AST analysis
    - Knowledge graph
    - Project profile via LLM
    - Vector store com metadados ricos

    repo_path pode ser:
    - Caminho local (C:\\projetos\\repo)
    - URL do GitHub (https://github.com/user/repo)
    """
    def emit(stage: str, data: dict):
        if on_progress:
            on_progress(stage, data)

    from agents.repo_loader import resolve_repo_input, is_github_url

    if is_github_url(repo_path):
        emit("cloning", {"message": "URL GitHub detectada"})
        try:
            def clone_progress(msg):
                # Cada linha do git vira um evento separado
                emit("cloning", {"message": msg})

            local_path = resolve_repo_input(repo_path, on_progress=clone_progress)
            emit("cloning", {"message": f"✓ Clone OK: {local_path}"})
            repo_path = local_path
        except Exception as e:
            err_msg = f"Falha ao clonar: {str(e)}"
            print(f"[ERROR] {err_msg}")
            emit("error", {"message": err_msg})
            raise RuntimeError(err_msg) from e
    else:
        try:
            repo_path = resolve_repo_input(repo_path)
        except (FileNotFoundError, NotADirectoryError) as e:
            err_msg = str(e)
            emit("error", {"message": err_msg})
            raise

    repo_path = os.path.abspath(repo_path)
    root = Path(repo_path)

    if not collection_name:
        collection_name = "repo_" + hashlib.md5(repo_path.encode()).hexdigest()[:12]

    cache = get_cache()

    emit("collecting", {"message": "Coletando arquivos..."})
    all_candidates = []
    for fp in root.rglob("*"):
        try:
            if (fp.is_file()
                and not any(part in IGNORE_DIRS for part in fp.parts)
                and fp.suffix in SUPPORTED_EXTENSIONS
                and fp.stat().st_size <= 500_000):
                all_candidates.append(fp)
        except OSError:
            continue

    files = collect_files(repo_path)
    if len(files) < len(all_candidates):
        emit("collecting", {
            "message": f"{len(files)} arquivos selecionados (de {len(all_candidates)} totais — priorizando código fonte)",
            "count": len(files),
            "total_available": len(all_candidates),
        })
    else:
        emit("collecting", {"message": f"{len(files)} arquivos encontrados", "count": len(files)})
    emit("detecting", {"message": "Detectando stack do projeto..."})
    project_type = detect_project_type(files)
    emit("detecting", {
        "message": "Stack detectada",
        "stack": project_type.get("stack", []),
        "frameworks": project_type.get("frameworks", []),
    })
    emit("analyzing", {"message": "Analisando estrutura do código (AST)..."})
    analyses = []
    docs = []
    code_files = [f for f in files if f.suffix in CODE_EXTENSIONS]

    for i, fp in enumerate(files):
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue

            cache_key = f"ast:{file_hash(fp)}"
            if fp.suffix in CODE_EXTENSIONS:
                cached = cache.get(cache_key)
                if cached is not None:
                    analysis_dict = cached
                    from agents.code_analyzer import Symbol
                    syms = [Symbol(**s) for s in analysis_dict.get("symbols", [])]
                    analysis = FileAnalysis(
                        path=analysis_dict["path"],
                        language=analysis_dict["language"],
                        loc=analysis_dict["loc"],
                        imports=analysis_dict.get("imports", []),
                        symbols=syms,
                    )
                else:
                    analysis = analyze_file(fp, content)
                    cache.set(cache_key, analysis.to_dict(), expire=86400 * 7)
                analyses.append(analysis)

            rel = str(fp.relative_to(root))
            metadata = {
                "file": rel,
                "extension": fp.suffix,
                "language": analysis.language if fp.suffix in CODE_EXTENSIONS else "text",
            }
            if fp.suffix in CODE_EXTENSIONS:
                metadata["symbols"] = ", ".join(s.name for s in analysis.symbols[:20])

            docs.append(Document(page_content=content, metadata=metadata))

            if (i + 1) % 25 == 0:
                emit("analyzing", {
                    "message": f"Analisado {i + 1}/{len(files)}",
                    "progress": (i + 1) / len(files),
                })
        except Exception as e:
            continue

    emit("analyzing", {"message": f"AST completo: {len(analyses)} arquivos de código", "count": len(analyses)})

    # 4. Knowledge graph
    emit("graphing", {"message": "Construindo grafo de conhecimento..."})
    graph = build_knowledge_graph(analyses, root)
    graph_info = graph_summary(graph)
    emit("graphing", {
        "message": "Grafo construído",
        "files": graph_info["files_count"],
        "symbols": graph_info["symbols_count"],
        "imports": graph_info["import_edges"],
    })

    # 5. Project profile via LLM
    emit("profiling", {"message": "Extraindo profile do projeto via LLM..."})
    llm = get_llm()
    profile = build_project_profile(analyses, project_type, graph_info, root, llm)
    emit("profiling", {"message": "Profile extraído", "profile": profile})

    # 6. Vector store
    emit("embedding", {"message": "Gerando embeddings..."})
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=150,
        separators=["\n\nclass ", "\n\ndef ", "\n\nfunction ", "\n\n", "\n", " "],
    )
    chunks = splitter.split_documents(docs)
    emit("embedding", {"message": f"{len(chunks)} chunks gerados", "count": len(chunks)})

    embeddings = get_embeddings()
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

    # Reset collection se já existir
    try:
        existing = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=persist_dir,
        )
        existing.delete_collection()
    except Exception:
        pass

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=persist_dir,
    )

    emit("done", {"message": "Indexação completa"})

    graph_full = serialize_graph_for_viz(graph, max_nodes=300)
    repo_meta = {
        "collection": collection_name,
        "repo_path": repo_path,
        "files_indexed": len(files),
        "code_files": len(analyses),
        "chunks": len(chunks),
        "profile": profile,
        "graph_info": {
            "files_count": graph_info["files_count"],
            "symbols_count": graph_info["symbols_count"],
            "import_edges": graph_info["import_edges"],
            "central_files": graph_info["central_files"],
        },
        "graph_full": graph_full,
    }
    cache.set(f"repo_meta:{collection_name}", repo_meta)

    return repo_meta


def load_vectorstore(collection_name: str) -> Chroma:
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    embeddings = get_embeddings()
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )


def get_repo_meta(collection_name: str) -> Optional[dict]:
    return get_cache().get(f"repo_meta:{collection_name}")


def list_indexed_repos() -> list[dict]:
    cache = get_cache()
    repos = []
    for key in list(cache.iterkeys()):
        if isinstance(key, str) and key.startswith("repo_meta:"):
            meta = cache.get(key)
            if meta:
                repos.append(meta)
    return repos
