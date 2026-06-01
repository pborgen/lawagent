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
from typing import Any, Optional

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

    # --- Model profile ---
    # Which chat-model + embeddings bundle to use. Profiles are defined in
    # config/profiles.yaml; this just names one. Unset → the YAML default.
    profile: Optional[str] = Field(default=None, alias="LAWAGENT_PROFILE")
    profiles_file: Optional[str] = Field(
        default=None,
        alias="LAWAGENT_PROFILES_FILE",
        description="Override path to the profiles YAML (default: config/profiles.yaml).",
    )
    pricing_file: Optional[str] = Field(
        default=None,
        alias="LAWAGENT_PRICING_FILE",
        description="Override path to the pricing YAML (default: config/pricing.yaml).",
    )
    states_file: Optional[str] = Field(
        default=None,
        alias="LAWAGENT_STATES_FILE",
        description="Override path to the per-state source registry "
        "(default: config/states.yaml).",
    )
    courtlistener_api_token: Optional[str] = Field(
        default=None,
        alias="COURTLISTENER_API_TOKEN",
        description="Free Law Project / CourtListener API token, used by "
        "`fetch-state --cases` to seed case law. Unset → case law is skipped.",
    )

    # --- Vector store (pgvector on Postgres) ---
    # Local dev / laptop ingest set LAWAGENT_PG_URL directly. In the cloud
    # the password lives in an RDS-managed Secrets Manager secret, so the
    # URL is taken apart: host/port/db arrive as env vars and the password
    # is fetched from pg_secret_arn at connect time (packages/db/session).
    pg_url: Optional[str] = Field(default=None, alias="LAWAGENT_PG_URL")
    pg_host: Optional[str] = Field(default=None, alias="LAWAGENT_PG_HOST")
    pg_port: int = Field(default=5432, alias="LAWAGENT_PG_PORT")
    pg_db: Optional[str] = Field(default=None, alias="LAWAGENT_PG_DB")
    pg_secret_arn: Optional[str] = Field(default=None, alias="LAWAGENT_PG_SECRET_ARN")

    # --- S3 fetcher (apps/s3fetch) ---
    # Default s3:// URI to mirror when `s3fetch pull` is run with no args.
    # AWS credentials and region come from the standard AWS chain.
    s3_uri: Optional[str] = Field(default=None, alias="LAWAGENT_S3_URI")
    # Override the directory name under data/case/s3/ when the prefix's
    # derived slug isn't what you want.
    s3_id: Optional[str] = Field(default=None, alias="LAWAGENT_S3_ID")

    # --- CT eFile scraper ---
    efile_username: Optional[str] = Field(default=None, alias="EFILE_USERNAME")
    efile_password: Optional[str] = Field(default=None, alias="EFILE_PASSWORD")
    efile_crn: Optional[str] = Field(default=None, alias="EFILE_CRN")
    efile_docket_no: Optional[str] = Field(default=None, alias="EFILE_DOCKET_NO")
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

    # --- Auth (Cognito + Google federation) -------------------------------
    # The FastAPI backend verifies every request's bearer token against the
    # Cognito user pool's JWKS and rejects any email not in
    # cognito_allowed_emails. Setting auth_disabled bypasses verification
    # entirely — dev only, never in App Runner.
    cognito_region: Optional[str] = Field(default=None, alias="COGNITO_REGION")
    cognito_user_pool_id: Optional[str] = Field(
        default=None, alias="COGNITO_USER_POOL_ID"
    )
    cognito_client_id: Optional[str] = Field(default=None, alias="COGNITO_CLIENT_ID")
    # Additional Cognito app-client IDs whose tokens the API should accept,
    # beyond cognito_client_id. Comma-separated. Used to admit the native
    # mobile app client (apps/mobile), which is a separate public client and
    # so issues tokens with a different `aud`. Empty = web client only.
    cognito_extra_audiences: str = Field(
        default="", alias="COGNITO_EXTRA_AUDIENCES"
    )
    cognito_allowed_emails: str = Field(default="", alias="COGNITO_ALLOWED_EMAILS")
    # Subset of allowed users granted the admin dashboard (LLM usage
    # metering). Comma-separated emails; empty = no admins. Seeded onto the
    # user row at login (apps/api/users._upsert_user).
    admin_emails: str = Field(default="", alias="LAWAGENT_ADMIN_EMAILS")
    auth_disabled: bool = Field(default=False, alias="LAWAGENT_AUTH_DISABLED")

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

    def uses_db_secret(self) -> bool:
        """True when the DB password comes from a Secrets Manager secret
        (cloud) rather than an inline LAWAGENT_PG_URL (local dev)."""
        return bool(self.pg_secret_arn)

    def require_db_secret(self) -> tuple[str, int, str, str]:
        """Return (host, port, dbname, secret_arn) for secret-based connects."""
        if not (self.pg_host and self.pg_db and self.pg_secret_arn):
            raise RuntimeError(
                "Secret-based DB config incomplete. Set LAWAGENT_PG_HOST, "
                "LAWAGENT_PG_DB, and LAWAGENT_PG_SECRET_ARN — or use "
                "LAWAGENT_PG_URL for local dev."
            )
        return self.pg_host, self.pg_port, self.pg_db, self.pg_secret_arn

    def require_pg_url(self) -> str:
        if not self.pg_url:
            raise RuntimeError(
                "LAWAGENT_PG_URL is not set. Example: "
                "postgresql+psycopg://lawagent:lawagent@localhost:5432/lawagent"
            )
        return self.pg_url

    def allowed_email_set(self) -> set[str]:
        """Normalize cognito_allowed_emails into a lowercased set."""
        return {
            e.strip().lower()
            for e in self.cognito_allowed_emails.split(",")
            if e.strip()
        }

    def admin_email_set(self) -> set[str]:
        """Normalize admin_emails into a lowercased set."""
        return {
            e.strip().lower()
            for e in self.admin_emails.split(",")
            if e.strip()
        }

    def require_cognito(self) -> tuple[str, str, str]:
        """Return (region, user_pool_id, client_id) or raise if unset.

        Called by the FastAPI auth dependency when auth is enabled, so
        misconfig surfaces as a clear startup error instead of a 500
        on every request.
        """
        if not (self.cognito_region and self.cognito_user_pool_id and self.cognito_client_id):
            raise RuntimeError(
                "Cognito is not configured. Set COGNITO_REGION, "
                "COGNITO_USER_POOL_ID, and COGNITO_CLIENT_ID — or set "
                "LAWAGENT_AUTH_DISABLED=true for local dev."
            )
        return self.cognito_region, self.cognito_user_pool_id, self.cognito_client_id

    def cognito_audiences(self) -> list[str]:
        """Every Cognito app-client ID whose tokens the API accepts.

        Always includes the primary (web) client_id; appends any IDs from
        cognito_extra_audiences (e.g. the native mobile client). A token is
        valid when its `aud` matches any member. With the extra var unset,
        this is just [client_id] — identical to the single-audience behavior.
        """
        _, _, client_id = self.require_cognito()
        extra = [
            a.strip() for a in self.cognito_extra_audiences.split(",") if a.strip()
        ]
        return [client_id, *extra]

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
