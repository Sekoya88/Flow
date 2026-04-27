from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel


def get_chat_model(model_config: dict[str, Any], fallback_api_keys: dict[str, str | None]) -> BaseChatModel | None:
    """
    model_config shape: {"provider": "openai"|"anthropic"|"ollama", "model": str, "temperature": float}
    fallback_api_keys: {"openai": key, "anthropic": key}
    Returns None if the required key is missing.
    """
    provider = model_config.get("provider", "openai")
    model = model_config.get("model", "gpt-4o-mini")
    temperature = float(model_config.get("temperature", 0.2))

    if provider == "anthropic":
        api_key = model_config.get("api_key") or fallback_api_keys.get("anthropic")
        if not api_key:
            return None
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(api_key=api_key, model=model, temperature=temperature)

    if provider == "ollama":
        base_url = model_config.get("base_url") or "http://localhost:11434"
        from langchain_ollama import ChatOllama
        return ChatOllama(base_url=base_url, model=model, temperature=temperature)

    # default: openai
    api_key = model_config.get("api_key") or fallback_api_keys.get("openai")
    if not api_key:
        return None
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(api_key=api_key, model=model, temperature=temperature)
