from __future__ import annotations

from langchain_core.embeddings import Embeddings  # pyright: ignore[reportMissingImports]

from llm.profiles import EmbeddingsConfig, get_active_profile
from llm.usage import record_embedding


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

    The returned model is wrapped so every embed call is metered into the
    active usage recorder (`llm.usage`). The wrapper is transparent — it
    delegates to the real model and only adds bookkeeping.
    """
    cfg = get_active_profile().embeddings
    return _MeteredEmbeddings(build_embeddings(cfg), provider=cfg.provider, model=cfg.model)


def _estimate_tokens(text: str) -> int:
    """Rough token count. Embedding providers rarely report real usage, so
    we approximate ~4 characters per token — good enough for cost order of
    magnitude, and always flagged as an estimate on the stored row."""
    return max(1, len(text) // 4) if text else 0


class _MeteredEmbeddings(Embeddings):
    """Embeddings proxy that records an (estimated) token tally per call.

    Wraps the real model so the rest of the app — the pgvector store in
    particular — is unaware metering exists. Records on both the document
    (ingest) and query (retrieval) paths; no-ops when no recorder is set.
    """

    def __init__(self, inner: Embeddings, *, provider: str, model: str) -> None:
        self._inner = inner
        self._provider = provider
        self._model = model

    def _record(self, tokens: int) -> None:
        record_embedding(
            provider=self._provider,
            model=self._model,
            input_tokens=tokens,
            estimated=True,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._record(sum(_estimate_tokens(t) for t in texts))
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self._record(_estimate_tokens(text))
        return self._inner.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self._record(sum(_estimate_tokens(t) for t in texts))
        return await self._inner.aembed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        self._record(_estimate_tokens(text))
        return await self._inner.aembed_query(text)


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
