# RepoMind 🔍

> **Context-Aware AI Code Review** — AMD Developer Hackathon 2026

Sistema multi-agente que **aprende seu repositório** primeiro (AST + knowledge graph 3D), depois faz code review **contextualizado** dos seus PRs.

---

## 🎯 Diferenciais

1. **AST analysis** com tree-sitter — extrai símbolos, imports, dependências reais
2. **Knowledge graph 3D** interativo — Three.js, force-directed, mostra arquitetura visualmente
3. **Project profile automático** — arquitetura, padrões, convenções (via LLM)
4. **Multi-query retrieval** — busca por arquivo, símbolo e semântica
5. **Reviewer com few-shot** — exemplos de boa vs má justificativa
6. **Critic adversarial** — filtra issues genéricos antes do relatório
7. **Privacy first** — Ollama local, código nunca sai da sua máquina
8. **Secrets seguros** — config centralizado, mascaramento automático em logs

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────┐
│  INDEXER (1x por repo)                              │
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
│  Arquivos do contexto BRILHAM no grafo 3D em        │
│  tempo real durante a execução                      │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (Windows)

### Pré-requisitos
- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com/download/windows) instalado

### Setup automático

Na pasta do projeto:

```cmd
setup.bat
```

Faz tudo: cria venv, instala deps, baixa modelo Ollama, valida.

### Rodar

```cmd
:: Terminal 1
run_backend.bat

:: Terminal 2
run_frontend.bat
```

Abre http://localhost:5173

### Buildar como EXE

Pra gerar um `RepoMind.exe` único (frontend + backend num executável):

```cmd
build.bat
```

Resultado: `dist\RepoMind.exe` (~500MB). Veja **BUILD_EXE.md** pra detalhes.

---

## 🔐 Segurança das credenciais

API keys **NUNCA** ficam no código. Tudo passa pelo `.env`:

```
backend/.env             ← suas credenciais (NÃO committar)
backend/.env.example     ← template (pode committar)
backend/config.py        ← carrega e valida secrets
.gitignore               ← protege .env
```

O backend:
- Valida config no startup e falha cedo se faltar algo
- Mascara automaticamente qualquer credencial que apareça em logs
- Endpoint `/config` retorna info pública (provider/modelo) **sem keys**
- WebSockets sanitizam mensagens antes de enviar ao frontend

Trocar de provider (Ollama → AMD Cloud → Groq) é só editar `.env`. Zero código alterado.

---

## 🎨 Interface

**Knowledge Graph 3D** (Three.js):
- Nodes = arquivos, tamanho proporcional a LOC
- Cores por linguagem
- Edges = imports
- Drag pra rotacionar, scroll pra zoom, click nos nodes
- **Durante o review, arquivos do contexto pulsam em vermelho** mostrando exatamente o que o RAG recuperou

**Pipeline visualizer** ao vivo:
- Cada agente acende verde com timing
- Mostra queries usadas, contexto recuperado, issues levantados vs filtrados pelo Critic

---

## 📁 Estrutura

```
repomind/
├── setup.bat              ← setup automático Windows
├── run_backend.bat        ← liga backend
├── run_frontend.bat       ← liga frontend
├── README.md
├── .gitignore             ← protege secrets
│
├── backend/
│   ├── config.py          ← config + sanitização de secrets
│   ├── agents/
│   │   ├── llm_client.py
│   │   ├── code_analyzer.py    ← AST com tree-sitter
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

## 🔧 Trocar provider

Edita `backend/.env`:

**Ollama (default, local)**
```
AMD_BASE_URL=http://localhost:11434/v1
AMD_API_KEY=ollama
AMD_MODEL=qwen2.5-coder:14b
```

**AMD Developer Cloud** (quando créditos chegarem)
```
AMD_BASE_URL=https://api.amd.com/v1
AMD_API_KEY=sua_amd_key
AMD_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
```

**Groq** (gratuito, rápido)
```
AMD_BASE_URL=https://api.groq.com/openai/v1
AMD_API_KEY=gsk_...
AMD_MODEL=qwen-2.5-coder-32b
```

---

## 🎬 Demo flow

1. Aponta pra um projeto Python real (FastAPI/Django/qualquer coisa)
2. **Indexação ao vivo** → grafo 3D aparece, profile extraído
3. Cola um diff que viola um padrão específico do projeto
4. **Pipeline streaming** → cada agente acende, contexto é recuperado
5. **Arquivos relevantes pulsam no grafo 3D** ← este é o "wow moment"
6. Resultado: issues com justificativa específica do projeto

---

## ⚙️ Stack

| Componente | Tech |
|---|---|
| Orquestração | LangGraph |
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

**"AMD_API_KEY não configurada"**
→ `cd backend && copy .env.example .env`

**"Não consegui conectar em localhost:11434"**
→ Ollama não tá rodando. Abre o app (ícone na bandeja) ou `ollama serve`.

**"Modelo não instalado"**
→ `ollama pull qwen2.5-coder:14b`

**Pipeline lento**
→ Verifica no Task Manager se a GPU tá sendo usada. Se cair na CPU, reinstala drivers NVIDIA. Ou usa modelo menor: `ollama pull qwen2.5-coder:7b`

**Grafo 3D não aparece**
→ Indexa um repo primeiro (passo 01 da UI). Depois selecione ele em "REPOS".
