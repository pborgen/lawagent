"""App-data persistence (users, projects) on Postgres.

Reuses the same `LAWAGENT_PG_URL` that pgvector uses, so the API only
opens one database connection pool. pgvector's `langchain_pg_*` tables
and these app tables share the same database but live in separate
namespaces — no schema conflicts.

Why SQLAlchemy ORM and not raw psycopg?
  - Two related tables now, more coming. The ORM removes the boilerplate
    of hand-rolling SELECT/INSERT for every CRUD route.
  - The same `Session` plugs straight into a FastAPI dependency.

Schema lifecycle:
  - `bootstrap_schema()` runs `Base.metadata.create_all()` once at API
    startup. Acceptable for a small app-data schema with a single
    deployment. The day we add destructive migrations, swap this for
    Alembic — until then, IF NOT EXISTS is enough.
"""
from __future__ import annotations

from db.models import Base, LlmUsageEvent, Project, User
from db.session import (
    bootstrap_schema,
    db_session,
    get_db_session,
    get_engine,
)
from db.usage import (
    UsageOverview,
    UsageRow,
    record_usage_events,
    usage_overview,
)


__all__ = [
    "Base",
    "Project",
    "User",
    "LlmUsageEvent",
    "bootstrap_schema",
    "db_session",
    "get_db_session",
    "get_engine",
    "record_usage_events",
    "usage_overview",
    "UsageOverview",
    "UsageRow",
]
