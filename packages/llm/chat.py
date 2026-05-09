from __future__ import annotations

import os
from typing import Optional

from langchain_core.language_models import BaseChatModel


# To add a new provider:
#   1. Add it to PROVIDERS below.
#   2. Implement the constructor in `_build_model`.
#   3. Add a default model entry to DEFAULT_MODELS.

PROVIDERS = ("anthropic", "openai")

DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-opus-4-7",
    "openai": "gpt-4o",
}


def get_chat_model(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """Return a configured LangChain chat model.

    Resolution order for each parameter:
        1. Explicit argument.
        2. Environment variable.
        3. Hard-coded default in this module.

    Environment variables:
        LAWAGENT_LLM_PROVIDER     'anthropic' (default) | 'openai'
        LAWAGENT_LLM_MODEL        provider-specific model id
        LAWAGENT_LLM_TEMPERATURE  float, default 0
        LAWAGENT_LLM_MAX_TOKENS   int, default 4096
    """
    provider = (provider or os.getenv("LAWAGENT_LLM_PROVIDER") or "anthropic").lower()
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown LAWAGENT_LLM_PROVIDER={provider!r}. "
            f"Supported: {', '.join(PROVIDERS)}."
        )

    model = model or os.getenv("LAWAGENT_LLM_MODEL") or DEFAULT_MODELS[provider]

    if temperature is None:
        temperature = float(os.getenv("LAWAGENT_LLM_TEMPERATURE", "0"))
    if max_tokens is None:
        max_tokens = int(os.getenv("LAWAGENT_LLM_MAX_TOKENS", "4096"))

    return _build_model(provider, model, temperature, max_tokens)


def _build_model(
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> BaseChatModel:
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(f"Unhandled provider: {provider!r}")
