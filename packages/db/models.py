"""SQLAlchemy ORM models for app data (users, projects).

Naming conventions:
  - Tables go under the `lawagent_*` prefix so they can't collide with
    the `langchain_pg_*` tables that pgvector creates in the same DB.
  - `cognito_sub` is the stable primary key from Cognito's ID token. We
    do not key on email — emails change, subs don't.
  - Timestamps are timezone-aware UTC.

Project model:
  - `owner_sub` is a FK to `lawagent_users.cognito_sub`. CASCADE on
    delete so removing a user removes their projects (we'll also need
    to GC their S3 prefix, but that's a separate concern).
  - `slug` is a URL-safe identifier the UI can show in breadcrumbs.
    Unique per owner, not globally — two users can both have a
    project called "smith-v-smith".
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for every app-data model."""


class User(Base):
    __tablename__ = "lawagent_users"

    # Cognito's stable subject claim — never reused, never editable.
    cognito_sub: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Grants access to the admin dashboard (usage metering). Seeded from
    # LAWAGENT_ADMIN_EMAILS on login (see apps/api/users._upsert_user), so
    # it's never edited by hand — flip the env var and re-login.
    is_admin: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class Project(Base):
    __tablename__ = "lawagent_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    owner_sub: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("lawagent_users.cognito_sub", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Human-readable label shown in the UI ("Smith v. Smith — divorce").
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # URL-safe identifier; user-visible in paths. Generated from `name`
    # when the project is created, editable later.
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    # Free-form long description (case background, opposing counsel, etc.).
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Loose categorization so the UI can offer divorce-tailored
    # workflows on divorce projects without locking us into an enum.
    matter_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    owner: Mapped[User] = relationship(back_populates="projects")

    __table_args__ = (
        UniqueConstraint("owner_sub", "slug", name="uq_lawagent_projects_owner_slug"),
    )


class LlmUsageEvent(Base):
    """One metered LLM call — a chat completion or an embedding batch.

    Written by the API after each /chat request (apps/api/main.py) from the
    events the `llm.usage` recorder collected. The admin dashboard
    aggregates this table by user, by model, and over time.

    `user_sub` is nullable so non-request work (e.g. ingest) can still be
    metered without a user, and ON DELETE SET NULL so usage history
    survives a user deletion (we want the spend record even if the account
    goes away). `project_id` is likewise SET NULL — usage outlives the
    project it was attributed to.
    """

    __tablename__ = "lawagent_llm_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    user_sub: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("lawagent_users.cognito_sub", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(),
        ForeignKey("lawagent_projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    # "chat" | "embedding"
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # True when token counts are heuristic (embeddings, or chat models that
    # don't report usage) rather than provider-reported.
    tokens_estimated: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False
    )
    # Estimated USD, computed at write time from config/pricing.yaml. NULL
    # for models we don't have a price for (e.g. fully local models).
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    # Agent answer mode for chat events ("short" | "memo" | "annotate").
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    __table_args__ = (
        # Aggregations group/sort by user-over-time and by model-over-time.
        Index("ix_lawagent_llm_usage_user_created", "user_sub", "created_at"),
        Index("ix_lawagent_llm_usage_model_created", "model", "created_at"),
    )
