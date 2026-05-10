"""
Valida que o setup está completo: dependências, .env, conexão com LLM.
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))


def check(name, fn):
    try:
        result = fn()
        if result:
            print(f"  \033[32mOK\033[0m {name}: {result}")
        else:
            print(f"  \033[32mOK\033[0m {name}")
        return True
    except Exception as e:
        print(f"  \033[31mFAIL\033[0m {name}: {type(e).__name__}: {e}")
        return False


def _try_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def main():
    print("\n\033[36m=== Validacao de Setup do RepoMind ===\033[0m\n")

    # ── 1. Dependências
    print("\033[33m[1] Dependencias Python\033[0m")
    deps = [
        ("langgraph", lambda: __import__("langgraph").__name__),
        ("langchain", lambda: __import__("langchain").__name__),
        ("langchain_openai", lambda: __import__("langchain_openai").__name__),
        ("chromadb", lambda: __import__("chromadb").__name__),
        ("fastapi", lambda: __import__("fastapi").__name__),
        ("tree-sitter (pack ou languages)", lambda: (
            __import__("tree_sitter_language_pack").__name__
            if _try_import("tree_sitter_language_pack")
            else __import__("tree_sitter_languages").__name__
        )),
        ("diskcache", lambda: __import__("diskcache").__name__),
        ("networkx", lambda: __import__("networkx").__name__),
        ("unidiff", lambda: __import__("unidiff").__name__),
        ("sentence_transformers", lambda: __import__("sentence_transformers").__name__),
    ]
    deps_ok = all(check(name, fn) for name, fn in deps)
    if not deps_ok:
        print("\n\033[31mInstale as deps faltantes: pip install -r requirements.txt\033[0m")
        sys.exit(1)

    # ── 2. .env
    print("\n\033[33m[2] Arquivo .env\033[0m")
    from dotenv import load_dotenv
    env_path = ROOT / "backend" / ".env"
    if not env_path.exists():
        print(f"  \033[31mFAIL\033[0m {env_path} nao existe")
        print(f"  Rode: copy .env.example .env")
        sys.exit(1)
    load_dotenv(env_path)

    env_vars = ["AMD_BASE_URL", "AMD_API_KEY", "AMD_MODEL"]
    env_ok = True
    for var in env_vars:
        val = os.getenv(var, "")
        if not val or val.startswith("your_") or val.startswith("sua_"):
            print(f"  \033[31mFAIL\033[0m {var}: nao configurado")
            env_ok = False
        else:
            display = val if "KEY" not in var else f"{val[:6]}..."
            if len(display) > 50:
                display = display[:47] + "..."
            print(f"  \033[32mOK\033[0m {var}: {display}")

    if not env_ok:
        print("\n\033[31mConfigure todas as variaveis em backend/.env\033[0m")
        sys.exit(1)

    # ── 3. Detecta provider
    base_url = os.getenv("AMD_BASE_URL", "")
    is_ollama = "11434" in base_url or "ollama" in base_url.lower()
    provider = "OLLAMA (local)" if is_ollama else "Cloud (OpenAI-compatible)"
    print(f"\n\033[36m[i] Provider detectado: {provider}\033[0m")

    # ── 4. Se Ollama, verifica que está rodando e o modelo existe
    if is_ollama:
        print("\n\033[33m[3] Ollama running\033[0m")
        try:
            import httpx
            import urllib.parse
            host = base_url.replace("/v1", "").rstrip("/")
            r = httpx.get(f"{host}/api/tags", timeout=5)
            if r.status_code != 200:
                print(f"  \033[31mFAIL\033[0m Ollama respondeu {r.status_code}")
                print(f"  Verifique se Ollama esta rodando (icone na bandeja)")
                sys.exit(1)
            data = r.json()
            models = [m["name"] for m in data.get("models", [])]
            print(f"  \033[32mOK\033[0m Ollama em {host}")
            print(f"     Modelos instalados: {len(models)}")
            for m in models[:8]:
                print(f"       - {m}")

            target_model = os.getenv("AMD_MODEL")
            if target_model not in models:
                # Verifica se algum model match o prefix
                matched = [m for m in models if m.startswith(target_model.split(":")[0])]
                if not matched:
                    print(f"\n  \033[31mFAIL\033[0m Modelo '{target_model}' nao instalado")
                    print(f"  Rode: ollama pull {target_model}")
                    sys.exit(1)
                else:
                    print(f"  \033[33mWARN\033[0m '{target_model}' nao encontrado exato, mas '{matched[0]}' existe")
        except httpx.ConnectError:
            print(f"  \033[31mFAIL\033[0m Nao consegui conectar em {base_url}")
            print(f"  - Confirma que Ollama esta rodando (icone na bandeja)")
            print(f"  - Tenta: ollama --version")
            sys.exit(1)

    # ── 5. Conexão LLM (chamada real)
    print("\n\033[33m[4] Conexao LLM (teste real)\033[0m")
    try:
        from agents.llm_client import get_llm, get_llm_info
        info = get_llm_info()
        print(f"  Provider: {info['provider']}, Model: {info['model']}")

        llm = get_llm()
        print(f"  Enviando prompt de teste... (pode demorar 10-30s na primeira vez)")
        response = llm.invoke("Reply with exactly the word: PONG")
        text = response.content.strip()
        if "PONG" in text.upper():
            print(f"  \033[32mOK\033[0m LLM respondeu: {text[:60]}")
        else:
            print(f"  \033[33mWARN\033[0m LLM respondeu mas nao com PONG: {text[:80]}")
    except Exception as e:
        print(f"  \033[31mFAIL\033[0m: {type(e).__name__}: {e}")
        if is_ollama:
            print(f"  Dica: o modelo precisa estar instalado e Ollama rodando.")
            print(f"        Tenta: ollama run {os.getenv('AMD_MODEL')}")
        sys.exit(1)

    # ── 6. Embeddings
    print("\n\033[33m[5] Embeddings (HuggingFace local)\033[0m")
    try:
        from agents.indexer import get_embeddings
        print(f"  Carregando modelo de embeddings... (primeira vez baixa ~80MB)")
        emb = get_embeddings()
        vec = emb.embed_query("test")
        print(f"  \033[32mOK\033[0m Embedding dim: {len(vec)}")
    except Exception as e:
        print(f"  \033[31mFAIL\033[0m: {e}")
        sys.exit(1)

    # ── 7. Tree-sitter
    print("\n\033[33m[6] Tree-sitter (AST parsing)\033[0m")
    try:
        from agents.code_analyzer import HAS_TREE_SITTER
        if HAS_TREE_SITTER:
            print(f"  \033[32mOK\033[0m tree-sitter disponivel")
        else:
            print(f"  \033[33mWARN\033[0m tree-sitter nao disponivel, usando regex fallback")
    except Exception as e:
        print(f"  \033[31mFAIL\033[0m: {e}")

    print("\n\033[32m=== Setup OK ===\033[0m\n")
    print("Proximos passos:")
    print("  1. Backend:  cd backend && uvicorn api.main:app --reload --port 8000")
    print("  2. Teste:    python scripts\\test_e2e.py <caminho_do_repo>")
    print("  3. Frontend: cd frontend && npm install && npm run dev")
    print()


if __name__ == "__main__":
    main()
