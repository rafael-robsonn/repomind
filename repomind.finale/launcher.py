"""
RepoMind launcher - inicia FastAPI e abre o navegador.
Entry point quando você roda RepoMind.exe.
"""
import sys
import os
import threading
import time
import webbrowser
from pathlib import Path


# Detecta se está rodando como EXE PyInstaller
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(sys.executable).parent
    IS_FROZEN = True
else:
    BUNDLE_DIR = Path(__file__).parent
    APP_DIR = BUNDLE_DIR
    IS_FROZEN = False


# Storage do usuário fica AO LADO do EXE, não dentro
os.chdir(APP_DIR)
os.environ.setdefault("CHROMA_PERSIST_DIR", str(APP_DIR / "chroma_db"))

# Adiciona backend ao path
sys.path.insert(0, str(BUNDLE_DIR / "backend"))


def open_browser_when_ready(url: str, timeout: int = 60):
    """Polling até servidor responder, aí abre browser."""
    try:
        import httpx
    except ImportError:
        time.sleep(3)
        webbrowser.open(url)
        return

    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{url}/health", timeout=1.5)
            if r.status_code == 200:
                time.sleep(0.5)
                webbrowser.open(url)
                return
        except Exception:
            pass
        time.sleep(0.5)
    print(f"\n[WARN] Servidor não respondeu em {timeout}s. Abra manualmente: {url}")


def show_banner():
    print(r"""
    ____                  __  ____           __
   / __ \___  ____  ____ /  |/  (_)___  ____/ /
  / /_/ / _ \/ __ \/ __ \/ /|_/ / / __ \/ __  /
 / _, _/  __/ /_/ / /_/ / /  / / / / / / /_/ /
/_/ |_|\___/ .___/\____/_/  /_/_/_/ /_/\__,_/
          /_/
    """)
    print("  Context-Aware AI Code Review")
    print("  http://localhost:8000")
    print()


def setup_env():
    """Garante .env existe na pasta do app."""
    env_path = APP_DIR / "backend" / ".env"
    if env_path.exists():
        return

    env_path.parent.mkdir(parents=True, exist_ok=True)

    # Tenta copiar do bundle, ou cria default
    bundle_env = BUNDLE_DIR / "backend" / ".env.example"
    if bundle_env.exists():
        env_path.write_text(bundle_env.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[INFO] Criado {env_path}")
    else:
        env_path.write_text(
            "AMD_BASE_URL=http://localhost:11434/v1\n"
            "AMD_API_KEY=ollama\n"
            "AMD_MODEL=qwen2.5-coder:14b\n"
            "OLLAMA_NUM_CTX=8192\n"
            "OLLAMA_NUM_PREDICT=2048\n",
            encoding="utf-8"
        )
        print(f"[INFO] Criado {env_path} com config padrão Ollama")


def check_ollama():
    """Avisa se Ollama não tá rodando."""
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"[OK] Ollama rodando, {len(models)} modelos disponíveis")
            if not any("qwen2.5-coder" in m for m in models):
                print("[WARN] Modelo qwen2.5-coder não encontrado.")
                print("       Rode: ollama pull qwen2.5-coder:14b")
            return True
    except Exception:
        pass

    print()
    print("=" * 60)
    print("  AVISO: Ollama não detectado em localhost:11434")
    print("=" * 60)
    print("  RepoMind precisa do Ollama rodando.")
    print("  1. Baixe: https://ollama.com/download/windows")
    print("  2. Rode:  ollama pull qwen2.5-coder:14b")
    print()
    print("  Continuando assim mesmo (você pode iniciar o Ollama depois)...")
    print()
    return False


def main():
    show_banner()
    setup_env()
    check_ollama()

    # Abre browser numa thread separada
    threading.Thread(
        target=open_browser_when_ready,
        args=("http://localhost:8000",),
        daemon=True,
    ).start()

    print("[INFO] Iniciando servidor em http://localhost:8000 ...")
    print("[INFO] Pressione Ctrl+C pra encerrar.")
    print()

    # Importa só agora (depois de configurar env vars)
    import uvicorn
    from api.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Encerrando...")
        sys.exit(0)
    except Exception as e:
        import traceback
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        if IS_FROZEN:
            input("\nPressione Enter pra sair...")
        sys.exit(1)
