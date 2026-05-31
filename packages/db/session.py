"""SQLAlchemy engine + session, configured from LAWAGENT_PG_URL."""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base
from settings import get_settings


logger = logging.getLogger(__name__)


# Cache the fetched DB credentials briefly so we don't call Secrets
# Manager on every new pool connection. On an auth failure (a rotation we
# haven't picked up yet) we bust this and refetch — see _db_connect.
_SECRET_TTL_SECONDS = 300.0
_secret_cache: dict[str, object] = {"value": None, "at": 0.0}


def _fetch_db_secret(secret_arn: str, *, force: bool = False) -> dict:
    """Return {'username', 'password'} from the RDS-managed secret, cached."""
    now = time.monotonic()
    cached = _secret_cache["value"]
    if (
        not force
        and cached is not None
        and now - float(_secret_cache["at"]) < _SECRET_TTL_SECONDS  # type: ignore[arg-type]
    ):
        return cached  # type: ignore[return-value]
    import boto3  # local import: only needed in cloud/secret mode

    client = boto3.client("secretsmanager")  # region from AWS_REGION env
    raw = client.get_secret_value(SecretId=secret_arn)["SecretString"]
    creds = json.loads(raw)
    _secret_cache["value"] = creds
    _secret_cache["at"] = now
    return creds


def _db_connect():
    """psycopg connection factory for secret mode. Fetches the current
    password (cached); on an auth error from a just-rotated password it
    busts the cache and retries once."""
    import psycopg

    host, port, dbname, secret_arn = get_settings().require_db_secret()

    def _open(force: bool):
        creds = _fetch_db_secret(secret_arn, force=force)
        return psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=creds["username"],
            password=creds["password"],
            sslmode="require",
        )

    try:
        return _open(force=False)
    except psycopg.OperationalError:
        # Most likely the password rotated under our cache — refetch once.
        return _open(force=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """One process-wide engine (a single pool for app-data and vectors).

    Local dev uses LAWAGENT_PG_URL directly. In the cloud the password is
    in an RDS-managed Secrets Manager secret, so we connect through a
    `creator` that fetches current credentials — rotation is transparent
    and the password is never baked into a cached URL string.

    pool_pre_ping survives DB restarts and idle-killed connections.
    """
    settings = get_settings()
    if settings.uses_db_secret():
        return create_engine(
            "postgresql+psycopg://",
            creator=_db_connect,
            pool_pre_ping=True,
            future=True,
        )
    return create_engine(settings.require_pg_url(), pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def db_session() -> Iterator[Session]:
    """Context-managed session for scripts and tests.

    Commits on success, rolls back + re-raises on exception.
    """
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Iterator[Session]:
    """FastAPI dependency — one session per request.

    Use as `Annotated[Session, Depends(get_db_session)]`. The wrapping
    `try/finally` guarantees close even when the route raises.
    """
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


def bootstrap_schema() -> None:
    """Enable pgvector and CREATE TABLE IF NOT EXISTS for every model.

    Called once from the API's lifespan, and safe to run by hand against a
    fresh database (e.g. a new RDS instance) before the first ingest:

        LAWAGENT_PG_URL=... python -c "from db import bootstrap_schema; bootstrap_schema()"

    The `CREATE EXTENSION` mirrors what docker/initdb does for local dev —
    RDS has no init hook, and the vector store assumes the extension is
    already present (see packages/store/pgvector.py). Idempotent: a no-op
    when the extension and tables already exist. The connecting role must
    be allowed to CREATE EXTENSION — the RDS master user can; a future
    least-privilege app user would need it enabled for it once. Does NOT
    alter existing tables; that's Alembic's job when we get there.
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    # create_all() creates new tables but never alters existing ones, so a
    # column added to a table that already exists needs an explicit, idempotent
    # ALTER. Postgres supports ADD COLUMN IF NOT EXISTS, which keeps this a
    # no-op once applied. (When destructive migrations arrive, this moves to
    # Alembic.)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE lawagent_users "
                "ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
    logger.info("App-data schema bootstrap complete (pgvector enabled).")
