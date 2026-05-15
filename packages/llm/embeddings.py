from __future__ import annotations

from typing import Optional

from langchain_core.embeddings import Embeddings  # pyright: ignore[reportMissingImports]

from settings import get_settings


PROVIDERS = ("voyage", "openai")

DEFAULT_MODELS: dict[str, str] = {
    "voyage": "voyage-3",
    "openai": "text-embedding-3-small",
}


def get_embeddings(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Embeddings:
    """Return a configured LangChain embeddings model.

    Resolution order for each parameter:
        1. Explicit argument.
        2. Settings (env / .env).
        3. Hard-coded default in this module.
    """
    s = get_settings()
    provider = (provider or s.embeddings_provider).lower()
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown embeddings provider {provider!r}. "
            f"Supported: {', '.join(PROVIDERS)}."
        )

    model = model or s.embeddings_model or DEFAULT_MODELS[provider]

    if provider == "voyage":
        from langchain_voyageai import VoyageAIEmbeddings

        return VoyageAIEmbeddings(model=model)

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model)

    raise ValueError(f"Unhandled provider: {provider!r}")
