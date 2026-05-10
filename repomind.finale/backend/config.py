"""
Configuração centralizada com:
- Carregamento de .env
- Validação no startup
- Mascaramento automático de secrets em logs/UI
- Detecção de secrets vazados acidentalmente
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)

_SECRET_PATTERNS = [
    re.compile(r"(?:api[_-]?key|apikey|token|secret|password)[\"':=\s]+[\"']?([A-Za-z0-9_\-\.]{16,})"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),       # OpenAI-style
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),       # Groq
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),       # GitHub
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
]


class ConfigError(Exception):
    pass


class Config:
    """Acessor de config validado."""

    @staticmethod
    def get(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
        val = os.getenv(key, default)
        if required and (not val or val.startswith(("your_", "sua_", "<"))):
            raise ConfigError(
                f"Variável obrigatória '{key}' não configurada em .env. "
                f"Copie .env.example para .env e configure os valores."
            )
        return val

    # ── LLM ────────────────────────────────────────────────────────────
    @staticmethod
    def llm_base_url() -> str:
        return Config.get("AMD_BASE_URL", required=True)

    @staticmethod
    def llm_api_key() -> str:
        return Config.get("AMD_API_KEY", default="ollama")

    @staticmethod
    def llm_model() -> str:
        return Config.get("AMD_MODEL", required=True)

    @staticmethod
    def is_ollama() -> bool:
        url = Config.llm_base_url()
        return "11434" in url or "ollama" in url.lower()

    @staticmethod
    def ollama_num_ctx() -> int:
        return int(Config.get("OLLAMA_NUM_CTX", "8192"))

    @staticmethod
    def ollama_num_predict() -> int:
        return int(Config.get("OLLAMA_NUM_PREDICT", "2048"))

    # ── GitHub ─────────────────────────────────────────────────────────
    @staticmethod
    def github_token() -> Optional[str]:
        val = Config.get("GITHUB_TOKEN")
        if val and val.startswith(("your_", "sua_")):
            return None
        return val or None

    # ── Storage ────────────────────────────────────────────────────────
    @staticmethod
    def chroma_dir() -> str:
        return Config.get("CHROMA_PERSIST_DIR", "./chroma_db")

    # ── Public info (safe pra UI) ──────────────────────────────────────
    @staticmethod
    def public_info() -> dict:
        """Info que pode ser exposta pro frontend (sem secrets)."""
        return {
            "provider": "ollama" if Config.is_ollama() else "cloud",
            "model": Config.llm_model(),
            "base_url_host": _extract_host(Config.llm_base_url()),
            "has_github_token": bool(Config.github_token()),
        }


def _extract_host(url: str) -> str:
    """Extrai apenas o host de uma URL pra mostrar na UI."""
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1) if m else "local"


def mask_secrets(text: str) -> str:
    """Mascara qualquer credencial que apareça num texto."""
    if not text:
        return text
    masked = text
    for pattern in _SECRET_PATTERNS:
        masked = pattern.sub(r"***MASKED***", masked)
    return masked


def validate_startup() -> dict:
    """
    Valida config no boot. Retorna info pública.
    Chama isso em api/main.py no startup.
    """
    errors = []
    warnings = []

    try:
        Config.llm_base_url()
    except ConfigError as e:
        errors.append(str(e))

    try:
        Config.llm_model()
    except ConfigError as e:
        errors.append(str(e))

    api_key = os.getenv("AMD_API_KEY", "")
    if api_key.startswith(("your_", "sua_")):
        warnings.append("AMD_API_KEY parece ser placeholder. Atualize .env.")

    if not Config.is_ollama() and not api_key:
        warnings.append("Provider cloud sem API key configurada.")

    if errors:
        raise ConfigError("\n".join(errors))

    return {
        "ok": True,
        "warnings": warnings,
        "info": Config.public_info(),
    }
