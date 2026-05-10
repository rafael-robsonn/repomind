# RepoMind 🔍

> **Context-Aware AI Code Review** — AMD Developer Hackathon 2026

Multi-agent system that **learns your repository** first (AST + 3D knowledge graph), then runs **context-aware** code review on your PRs.

---

## 🎯 Key features

1. **AST analysis** with tree-sitter — extracts symbols, imports, real dependencies
2. **Interactive 3D knowledge graph** — Three.js, force-directed, visualizes architecture
3. **Automatic project profile** — architecture, patterns, conventions (via LLM)
4. **Multi-query retrieval** — search by file, symbol, and semantics
5. **Reviewer with few-shot** — examples of good vs. bad justification
6. **Adversarial Critic** — filters generic issues before the final report
7. **Privacy first** — local Ollama, your code never leaves your machine
8. **Secure secrets** — centralized config, automatic masking in logs

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│  INDEXER (runs once per repo)                       │
│  Files → AST (tree-sitter) → Knowledge Graph        │
│              ↓                                      │
│       Project Profile (LLM)                         │
│              ↓                                      │
│       Vector Store (ChromaDB)                       │
│              ↓                                      │
│       3D Graph (Three.js)                           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  REVIEW PIPELINE (LangGraph)                        │
│  Diff → Parse → Contextualize → Review              │
│                                     ↓               │
│                                  Critic             │
│                                     ↓               │
│                                  Report             │
│                                                     │
│  Context files GLOW in the 3D graph in real time    │
│  while the pipeline runs                            │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (Windows)

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com/download/windows) installed

### Automatic setup

From the project folder:

```cmd
setup.bat
```

Does everything: creates the venv, installs deps, pulls the Ollama model, validates.

### Run

```cmd
:: Terminal 1
run_backend.bat

:: Terminal 2
run_frontend.bat
```

Open http://localhost:5173

### Build as EXE

To produce a single `RepoMind.exe` (frontend + backend bundled):

```cmd
build.bat
```

Output: `dist\RepoMind.exe` (~500MB). See **BUILD_EXE.md** for details.

---

## 🔐 Credentials security

API keys are **NEVER** stored in code. Everything goes through `.env`:

```
backend/.env             ← your credentials (DO NOT commit)
backend/.env.example     ← template (safe to commit)
backend/config.py        ← loads and validates secrets
.gitignore               ← protects .env
```

The backend:
- Validates config on startup and fails fast if anything is missing
- Automatically masks any credential that shows up in logs
- The `/config` endpoint returns public info (provider/model) **without keys**
- WebSockets sanitize messages before sending them to the frontend

Switching providers (Ollama → AMD Cloud → Groq) is just editing `.env`. Zero code changes.

---

## 🎨 Interface

**3D Knowledge Graph** (Three.js):
- Nodes = files, size proportional to LOC
- Colors by language
- Edges = imports
- Drag to rotate, scroll to zoom, click nodes to inspect
- **During review, context files pulse in red** showing exactly what the RAG retrieved

**Live pipeline visualizer**:
- Each agent lights up green with timing
- Shows queries used, retrieved context, issues raised vs. filtered out by the Critic

---

## 📁 Structure

```
repomind/
├── setup.bat              ← automatic Windows setup
├── run_backend.bat        ← starts the backend
├── run_frontend.bat       ← starts the frontend
├── README.md
├── .gitignore             ← protects secrets
│
├── backend/
│   ├── config.py          ← config + secret sanitization
│   ├── agents/
│   │   ├── llm_client.py
│   │   ├── code_analyzer.py    ← AST via tree-sitter
│   │   ├── indexer.py          ← + serialize_graph_for_viz
│   │   ├── diff_parser.py
│   │   ├── contextualizer.py
│   │   ├── reviewer.py
│   │   └── pipeline.py
│   ├── api/main.py        ← + /config + /repos/{id}/graph
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── package.json       ← + three
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── components/
│           └── GraphViz3D.jsx   ← Three.js graph
│
├── scripts/
│   ├── validate_setup.py
│   └── test_e2e.py
│
└── sample_diffs/
```

---

## 🔧 Switching provider

Edit `backend/.env`:

**Ollama (default, local)**
```
AMD_BASE_URL=http://localhost:11434/v1
AMD_API_KEY=ollama
AMD_MODEL=qwen2.5-coder:14b
```

**AMD Developer Cloud** (when credits arrive)
```
AMD_BASE_URL=https://api.amd.com/v1
AMD_API_KEY=your_amd_key
AMD_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
```

**Groq** (free, fast)
```
AMD_BASE_URL=https://api.groq.com/openai/v1
AMD_API_KEY=gsk_...
AMD_MODEL=qwen-2.5-coder-32b
```

---

## 🎬 Demo flow

1. Point it at a real Python project (FastAPI/Django/anything)
2. **Live indexing** → 3D graph appears, profile extracted
3. Paste a diff that violates a project-specific pattern
4. **Streaming pipeline** → each agent lights up, context is retrieved
5. **Relevant files pulse in the 3D graph** ← this is the "wow moment"
6. Result: issues with project-specific justification

---

## ⚙️ Stack

| Component | Tech |
|---|---|
| Orchestration | LangGraph |
| LLM | Qwen2.5-Coder via Ollama / AMD ROCm |
| AST | tree-sitter |
| Embeddings | BAAI/bge-small-en-v1.5 (local CPU) |
| Vector Store | ChromaDB |
| Knowledge Graph | NetworkX + Three.js |
| Cache | DiskCache |
| Backend | FastAPI + WebSockets |
| Frontend | React + Vite + Three.js |

---

## 🐛 Troubleshooting

**"AMD_API_KEY not configured"**
→ `cd backend && copy .env.example .env`

**"Could not connect to localhost:11434"**
→ Ollama isn't running. Open the app (tray icon) or run `ollama serve`.

**"Model not installed"**
→ `ollama pull qwen2.5-coder:14b`

**Slow pipeline**
→ Check Task Manager to see if the GPU is actually being used. If it falls back to CPU, reinstall NVIDIA drivers. Or use a smaller model: `ollama pull qwen2.5-coder:7b`

**3D graph doesn't show up**
→ Index a repo first (step 01 in the UI). Then select it under "REPOS".
