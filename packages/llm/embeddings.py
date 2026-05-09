from __future__ import annotations

import os
from typing import Optional

from langchain_core.embeddings import Embeddings


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

    Environment variables:
        LAWAGENT_EMBEDDINGS         'voyage' (default) | 'openai'
        LAWAGENT_EMBEDDINGS_MODEL   provider-specific embedding model id
    """
    provider = (provider or os.getenv("LAWAGENT_EMBEDDINGS") or "voyage").lower()
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown LAWAGENT_EMBEDDINGS={provider!r}. "
            f"Supported: {', '.join(PROVIDERS)}."
        )

    model = model or os.getenv("LAWAGENT_EMBEDDINGS_MODEL") or DEFAULT_MODELS[provider]

    if provider == "voyage":
        from langchain_voyageai import VoyageAIEmbeddings

        return VoyageAIEmbeddings(model=model)

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model)

    raise ValueError(f"Unhandled provider: {provider!r}")
