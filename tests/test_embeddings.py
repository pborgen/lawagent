"""Unit tests for the model-profile system and the model builders."""
from __future__ import annotations

import pytest

from llm import active_collection, load_profiles
from llm.embeddings import build_embeddings
from llm.profiles import EmbeddingsConfig


def test_bundled_profiles_load_and_validate() -> None:
    cfg = load_profiles()
    # The YAML `default:` must name a real profile (validated on load).
    assert cfg.default in cfg.profiles
    assert "local" in cfg.profiles


def test_local_profile_pairs_chat_and_embeddings_locally() -> None:
    local = load_profiles().profiles["local"]
    assert local.chat.provider == "local"
    assert local.embeddings.provider == "local"


def test_active_collection_is_namespaced_by_embeddings_model() -> None:
    base = load_profiles().collection_base
    # Collection name = "<base>__<embeddings-model-slug>".
    assert active_collection().startswith(f"{base}__")


def test_build_embeddings_local_without_deps_raises() -> None:
    cfg = EmbeddingsConfig(provider="local", model="BAAI/bge-small-en-v1.5")
    try:
        import langchain_huggingface  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="uv sync --group local"):
            build_embeddings(cfg)
    else:
        pytest.skip("local deps installed — ImportError path not exercised")
