"""
LLM client - OpenAI-compatible endpoint.
Funciona com: Ollama (local), Groq, AMD Developer Cloud, OpenRouter, Together.ai.

NUNCA loga ou expõe API keys. Usa config centralizado.
"""
from langchain_openai import ChatOpenAI
from config import Config


def get_llm(temperature: float = 0.2):
    """
    Cliente LLM com config validada. API key NUNCA passa por logs ou UI.
    """
    extra_kwargs = {}

    if Config.is_ollama():
        extra_kwargs["model_kwargs"] = {
            "extra_body": {
                "options": {
                    "num_ctx": Config.ollama_num_ctx(),
                    "num_predict": Config.ollama_num_predict(),
                }
            }
        }

    return ChatOpenAI(
        base_url=Config.llm_base_url(),
        api_key=Config.llm_api_key(),
        model=Config.llm_model(),
        temperature=temperature,
        timeout=180,
        max_retries=2,
        **extra_kwargs,
    )


def get_llm_info() -> dict:
    """Info segura pra UI (sem credenciais)."""
    return Config.public_info()
