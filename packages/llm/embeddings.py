from __future__ import annotations

from langchain_core.embeddings import Embeddings  # pyright: ignore[reportMissingImports]

from llm.profiles import EmbeddingsConfig, get_active_profile


_LOCAL_DEPS_HINT = (
    "Install local embedding deps: uv sync --group local "
    "(or: pip install 'lawagent-monorepo[local]')"
)


def get_embeddings() -> Embeddings:
    """Return the embeddings model for the active profile.

    Which model this is — provider and name — is defined in
    `config/profiles.yaml` and selected by `LAWAGENT_PROFILE`. The
    embeddings model is bound to its profile's pgvector collection;
    switching profiles switches collections (see `llm.active_collection`).
    """
    return build_embeddings(get_active_profile().embeddings)


def build_embeddings(cfg: EmbeddingsConfig) -> Embeddings:
    """Construct a LangChain embeddings model from an `EmbeddingsConfig`."""
    if cfg.provider == "voyage":
        from langchain_voyageai import VoyageAIEmbeddings

        return VoyageAIEmbeddings(model=cfg.model)

    if cfg.provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=cfg.model)

    if cfg.provider == "bedrock":
        # Amazon Bedrock embeddings (e.g. amazon.titan-embed-text-v2:0,
        # cohere.embed-english-v3). Credentials/region come from the standard
        # AWS chain; the YAML may override region per profile.
        from langchain_aws import BedrockEmbeddings

        return BedrockEmbeddings(model_id=cfg.model, region_name=cfg.region)

    if cfg.provider == "ollama":
        # Embeddings served by the local Ollama daemon (e.g. nomic-embed-text,
        # mxbai-embed-large). The model must be pulled via `ollama pull`.
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=cfg.model)

    if cfg.provider == "local":
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:
            raise ImportError(_LOCAL_DEPS_HINT) from exc

        return HuggingFaceEmbeddings(
            model_name=cfg.model,
            model_kwargs={"device": cfg.device},
            encode_kwargs={"normalize_embeddings": True},
        )

    raise ValueError(f"Unhandled embeddings provider: {cfg.provider!r}")
