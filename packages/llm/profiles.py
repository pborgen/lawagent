"""Model profiles — the single definition of which model bundles exist.

A *profile* pairs a chat model with the embeddings model it must be used
with. Profiles are declared in `config/profiles.yaml`; this module loads
and validates that file, and resolves the active profile from
`LAWAGENT_PROFILE` (falling back to the YAML `default:`).

Why chat + embeddings travel together: a pgvector collection is built
with one specific embeddings model, so each profile gets its own
collection — see `active_collection()`. Switching profiles then never
queries vectors of the wrong dimension.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from settings import get_settings


ChatProvider = Literal["local", "ollama", "anthropic", "openai", "bedrock"]
EmbeddingsProvider = Literal["local", "ollama", "voyage", "openai", "bedrock"]


class ChatConfig(BaseModel):
    """Chat-model half of a profile."""

    provider: ChatProvider
    model: str
    temperature: float = 0.0
    max_tokens: int = 4096
    device: str = "cpu"  # `local` provider only: cpu | cuda | mps
    region: str | None = None  # `bedrock` provider only; falls back to AWS_REGION


class EmbeddingsConfig(BaseModel):
    """Embeddings half of a profile."""

    provider: EmbeddingsProvider
    model: str
    device: str = "cpu"  # `local` provider only: cpu | cuda | mps
    region: str | None = None  # `bedrock` provider only; falls back to AWS_REGION


class Profile(BaseModel):
    """One named chat + embeddings bundle."""

    description: str = ""
    chat: ChatConfig
    embeddings: EmbeddingsConfig


class ProfilesConfig(BaseModel):
    """The whole `config/profiles.yaml` document."""

    default: str
    collection_base: str = "ct-divorce"
    profiles: dict[str, Profile]

    @model_validator(mode="after")
    def _default_must_exist(self) -> "ProfilesConfig":
        if self.default not in self.profiles:
            raise ValueError(
                f"default profile {self.default!r} is not defined; "
                f"available: {', '.join(sorted(self.profiles))}"
            )
        return self


def _profiles_path() -> Path:
    """Locate the profiles YAML.

    Honors `LAWAGENT_PROFILES_FILE`; otherwise `config/profiles.yaml` at
    the repo root (two levels above this `packages/llm/` file).
    """
    override = get_settings().profiles_file
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "config" / "profiles.yaml"


@lru_cache(maxsize=1)
def load_profiles() -> ProfilesConfig:
    """Load and validate `config/profiles.yaml` (cached)."""
    path = _profiles_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Profiles file not found: {path}. "
            "Expected config/profiles.yaml at the repo root."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ProfilesConfig.model_validate(data)


def active_profile_name() -> str:
    """Name of the profile selected by `LAWAGENT_PROFILE`, or the default."""
    return get_settings().profile or load_profiles().default


def get_active_profile() -> Profile:
    """Return the active `Profile`.

    Raises a clear error if `LAWAGENT_PROFILE` names a profile that does
    not exist in the YAML.
    """
    cfg = load_profiles()
    name = active_profile_name()
    if name not in cfg.profiles:
        raise ValueError(
            f"Unknown profile {name!r} (LAWAGENT_PROFILE). "
            f"Available: {', '.join(sorted(cfg.profiles))}."
        )
    return cfg.profiles[name]


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def active_collection() -> str:
    """The pgvector collection name for the active profile.

    `<collection_base>__<embeddings-model-slug>` — so each embeddings
    model reads from and writes to its own collection.
    """
    cfg = load_profiles()
    return f"{cfg.collection_base}__{_slug(get_active_profile().embeddings.model)}"
