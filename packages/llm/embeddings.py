from __future__ import annotations

from typing import Optional

from langchain_core.embeddings import Embeddings  # pyright: ignore[reportMissingImports]

from settings import get_settings


PROVIDERS = ("voyage", "openai", "local")

DEFAULT_MODELS: dict[str, str] = {
    "voyage": "voyage-3",
    "openai": "text-embedding-3-small",
    # sentence-transformers on CPU; no API key. First run downloads weights.
    "local": "BAAI/bge-small-en-v1.5",
}

_LOCAL_DEPS_HINT = (
    "Install local embedding deps: uv sync --group local "
    "(or: pip install 'lawagent-monorepo[local]')"
)


def get_embeddings(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Embeddings:
    """Return a configured LangChain embeddings model.

    Resolution order for each parameter:
        1. Explicit argument.
        2. Settings (env / .env).
        3. Hard-coded default in this module.

    Switching providers changes vector dimension — re-ingest into a new
    collection (or drop the old one) before querying.
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

    if provider == "local":
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:
            raise ImportError(_LOCAL_DEPS_HINT) from exc

        return HuggingFaceEmbeddings(
            model_name=model,
            model_kwargs={"device": s.embeddings_device},
            encode_kwargs={"normalize_embeddings": True},
        )

    raise ValueError(f"Unhandled provider: {provider!r}")
