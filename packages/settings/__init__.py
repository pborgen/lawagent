"""Single source of truth for environment-driven config.

Every other module in the codebase reads configuration through
`from settings import get_settings` instead of calling `os.getenv()`
or `load_dotenv()` directly. The settings object reads from process
env (and `.env` if present in the working directory) exactly once;
subsequent calls return the cached instance.

To override a value in tests, call `get_settings.cache_clear()` after
mutating the env, or construct `Settings(field=value)` directly.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console


_INLINE_COMMENT = re.compile(r"\s+#.*$")


_console = Console(stderr=True)


# Load .env into os.environ at import time. Pydantic-Settings can read
# .env on its own, but it does NOT mutate os.environ — and the provider
# SDKs (langchain-anthropic, langchain-voyageai, langchain-openai) read
# their API keys directly from os.environ. Calling load_dotenv() here
# is the single place in the codebase that bridges the two.
load_dotenv()


LLMProvider = Literal["anthropic", "openai"]
EmbeddingsProvider = Literal["voyage", "openai"]


class Settings(BaseSettings):
    """All env-driven config, in one typed object.

    Field names are lowercase; the matching env var is given by `alias=`.
    Provider SDK keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, VOYAGE_API_KEY)
    are intentionally NOT modeled here — the SDKs read them from the
    environment themselves. They still belong in your .env.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # --- LLM (chat) ---
    llm_provider: LLMProvider = Field(
        default="anthropic", alias="LAWAGENT_LLM_PROVIDER"
    )
    llm_model: Optional[str] = Field(default=None, alias="LAWAGENT_LLM_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LAWAGENT_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, alias="LAWAGENT_LLM_MAX_TOKENS")

    # --- Embeddings ---
    embeddings_provider: EmbeddingsProvider = Field(
        default="voyage", alias="LAWAGENT_EMBEDDINGS"
    )
    embeddings_model: Optional[str] = Field(
        default=None, alias="LAWAGENT_EMBEDDINGS_MODEL"
    )

    # --- Vector store (pgvector on Postgres) ---
    pg_url: Optional[str] = Field(default=None, alias="LAWAGENT_PG_URL")

    # --- CT eFile scraper ---
    efile_username: Optional[str] = Field(default=None, alias="EFILE_USERNAME")
    efile_password: Optional[str] = Field(default=None, alias="EFILE_PASSWORD")
    efile_crn: Optional[str] = Field(default=None, alias="EFILE_CRN")
    efile_storage_state: str = Field(
        default="./data/case/efile/.storage_state.json",
        alias="EFILE_STORAGE_STATE",
    )
    efile_min_wait_seconds: float = Field(
        default=2.0, alias="EFILE_MIN_WAIT_SECONDS"
    )
    efile_max_wait_seconds: float = Field(
        default=5.0, alias="EFILE_MAX_WAIT_SECONDS"
    )
    efile_download_delay_seconds: float = Field(
        default=1.0, alias="EFILE_DOWNLOAD_DELAY_SECONDS"
    )

    @model_validator(mode="before")
    @classmethod
    def _strip_inline_comments(cls, data: Any) -> Any:
        """Normalize inline-comment-leakage from .env values.

        python-dotenv does NOT strip inline comments from values, so a
        line like `KEY=val   # comment` reads as `"val   # comment"`,
        and `KEY= # comment` reads as `" # comment"`. This validator
        runs on the merged source dict before per-field validation:
        - For every string value, drop a trailing ` # comment`.
        - If the cleaned value is empty or comment-only, omit the key
          entirely so the field default applies.
        """
        if not isinstance(data, dict):
            return data
        cleaned: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = _INLINE_COMMENT.sub("", value).strip()
                if not value or value.startswith("#"):
                    continue
            cleaned[key] = value
        return cleaned

    def require_pg_url(self) -> str:
        if not self.pg_url:
            raise RuntimeError(
                "LAWAGENT_PG_URL is not set. Example: "
                "postgresql+psycopg://lawagent:lawagent@localhost:5432/lawagent"
            )
        return self.pg_url

    def require_efile_credentials(self) -> tuple[str, str]:
        if not self.efile_username or not self.efile_password:
            raise RuntimeError(
                "EFILE_USERNAME and EFILE_PASSWORD must be set in your .env."
            )
        return self.efile_username, self.efile_password


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    cwd = Path.cwd()
    env_file = cwd / ".env"
    status = "found" if env_file.exists() else "[red]MISSING[/red]"
    _console.log(f"[dim]settings[/dim] cwd={cwd}  .env={status} ({env_file})")
    return Settings()


__all__ = ["Settings", "get_settings"]
