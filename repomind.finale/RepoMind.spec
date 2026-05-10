# RepoMind PyInstaller spec
# Gera um único RepoMind.exe contendo backend + frontend buildado.
#
# Uso: pyinstaller RepoMind.spec
#
# IMPORTANTE: o frontend precisa estar buildado em frontend/dist/ antes.
#             Roda `npm run build` no frontend primeiro, ou usa build.bat.

import os
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

block_cipher = None
ROOT = Path(SPECPATH)

# ── Datas: arquivos NÃO-Python que vão pro bundle ────────────────────────
datas = []

# Frontend buildado
frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.exists():
    datas.append((str(frontend_dist), "frontend_dist"))
else:
    print("=" * 60)
    print("AVISO: frontend/dist NÃO existe.")
    print("Rode `npm run build` no frontend antes de buildar o EXE.")
    print("=" * 60)

# .env.example pro launcher copiar
env_example = ROOT / "backend" / ".env.example"
if env_example.exists():
    datas.append((str(env_example), "backend"))

# Sample diffs (úteis pra demo)
sample_diffs = ROOT / "sample_diffs"
if sample_diffs.exists():
    datas.append((str(sample_diffs), "sample_diffs"))

# Tree-sitter shared libs (precisa empacotar manualmente)
# Tenta os dois pacotes possíveis
for ts_pkg in ["tree_sitter_language_pack", "tree_sitter_languages"]:
    try:
        datas += collect_data_files(ts_pkg)
    except Exception:
        pass

# Chromadb metadata
try:
    datas += copy_metadata("chromadb")
except Exception:
    pass

# Sentence transformers / huggingface metadata
for pkg in ["transformers", "tokenizers", "huggingface-hub", "torch", "tqdm", "numpy", "regex", "filelock", "packaging", "pyyaml", "safetensors"]:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass


# ── Hidden imports: módulos que o PyInstaller não detecta sozinho ────────
hiddenimports = [
    # FastAPI / Uvicorn
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",

    # ChromaDB
    "chromadb",
    "chromadb.telemetry.product.posthog",
    "chromadb.api.fastapi",
    "chromadb.db.impl",
    "chromadb.db.impl.sqlite",
    "onnxruntime",
    "tokenizers",
    "pkg_resources.py2_warn",

    # Tree-sitter (qualquer um dos dois pacotes)
    "tree_sitter",
    "tree_sitter_languages",
    "tree_sitter_language_pack",

    # LangChain
    "langchain_openai",
    "langchain_community",
    "langchain_community.vectorstores",
    "langchain_community.vectorstores.chroma",
    "langchain_community.embeddings",
    "langchain_community.embeddings.huggingface",
    "langchain_text_splitters",

    # LangGraph
    "langgraph",
    "langgraph.graph",

    # Embeddings
    "sentence_transformers",
    "sentence_transformers.SentenceTransformer",
    "transformers",
    "torch",

    # App modules
    "config",
    "agents",
    "agents.llm_client",
    "agents.code_analyzer",
    "agents.indexer",
    "agents.diff_parser",
    "agents.contextualizer",
    "agents.reviewer",
    "agents.pipeline",
    "api",
    "api.main",
]

# Coleta submódulos completos de pacotes problemáticos
hiddenimports += collect_submodules("chromadb")
hiddenimports += collect_submodules("langchain_community")
hiddenimports += collect_submodules("tiktoken_ext")


# ── Excludes: NÃO empacotar coisas que pesam e não usamos ───────────────
excludes = [
    "matplotlib", "pandas", "scipy", "PIL", "tkinter",
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "IPython", "jupyter", "notebook",
    "pytest", "test", "tests",
]


# ── Analysis ─────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT), str(ROOT / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Single-file EXE (onefile mode) ───────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="RepoMind",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # mostra terminal (importante pra ver logs/erros)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="icon.ico",      # adicione se tiver um ícone
)
