"""Unit tests for llm.get_embeddings provider wiring."""
from __future__ import annotations

import pytest

from llm.embeddings import DEFAULT_MODELS, PROVIDERS, get_embeddings


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unknown embeddings provider"):
        get_embeddings(provider="ollama")


def test_local_provider_without_deps_raises() -> None:
    try:
        import langchain_huggingface  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="uv sync --group local"):
            get_embeddings(provider="local")
    else:
        pytest.skip("local deps installed — ImportError path not exercised")


def test_providers_include_local() -> None:
    assert "local" in PROVIDERS
    assert DEFAULT_MODELS["local"].startswith("BAAI/")
