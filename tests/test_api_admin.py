"""Tests for the admin dashboard router and /me identity endpoint.

Offline: a SQLite in-memory engine stands in for Postgres, and the auth
dependency is overridden to a chosen `AuthUser`. Admin status is driven
the real way — through `LAWAGENT_ADMIN_EMAILS` — so we exercise the same
seeding path (`_upsert_user`) production uses.

The property we guard: a non-admin (any allowlisted user) is 403'd from
the usage endpoint and sees `is_admin: false` on /me, while an admin gets
the aggregated overview.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.admin import router as admin_router
from api.auth import AuthUser, require_user
from api.users import router as users_router
from db.models import Base, LlmUsageEvent, User
from db.session import get_db_session
from settings import get_settings


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture()
def set_admins(monkeypatch):
    """Set LAWAGENT_ADMIN_EMAILS and bust the settings cache."""

    def _apply(emails: str) -> None:
        monkeypatch.setenv("LAWAGENT_ADMIN_EMAILS", emails)
        get_settings.cache_clear()

    yield _apply
    get_settings.cache_clear()


def _make_client(session_factory, auth_user: AuthUser) -> TestClient:
    app = FastAPI()
    app.include_router(users_router)
    app.include_router(admin_router)

    def _override_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[require_user] = lambda: auth_user
    return TestClient(app)


def _user(sub: str, email: str) -> AuthUser:
    return AuthUser(sub=sub, email=email, claims={"sub": sub, "email": email})


# --- /me -----------------------------------------------------------------


def test_me_reports_admin_flag(session_factory, set_admins):
    set_admins("boss@example.com")
    admin = _make_client(session_factory, _user("boss-sub", "boss@example.com"))
    regular = _make_client(session_factory, _user("reg-sub", "reg@example.com"))

    a = admin.get("/me").json()
    assert a["is_admin"] is True
    assert a["email"] == "boss@example.com"

    r = regular.get("/me").json()
    assert r["is_admin"] is False


def test_admin_status_tracks_env_on_relogin(session_factory, set_admins):
    """Granting admin is an env change that takes effect on next request."""
    set_admins("")  # nobody is admin yet
    client = _make_client(session_factory, _user("u-sub", "u@example.com"))
    assert client.get("/me").json()["is_admin"] is False

    set_admins("u@example.com")  # grant
    assert client.get("/me").json()["is_admin"] is True


# --- /admin/usage/overview ----------------------------------------------


def test_overview_forbidden_for_non_admin(session_factory, set_admins):
    set_admins("boss@example.com")
    regular = _make_client(session_factory, _user("reg-sub", "reg@example.com"))
    assert regular.get("/admin/usage/overview").status_code == 403


def test_overview_aggregates_for_admin(session_factory, set_admins):
    set_admins("boss@example.com")
    admin = _make_client(session_factory, _user("boss-sub", "boss@example.com"))

    # Seed the admin row (via /me) and insert usage events directly.
    admin.get("/me")
    with session_factory() as s:
        s.add(User(cognito_sub="alice", email="alice@example.com"))
        s.add_all(
            [
                LlmUsageEvent(
                    user_sub="alice",
                    kind="chat",
                    provider="anthropic",
                    model="claude-opus-4-7",
                    input_tokens=1000,
                    output_tokens=500,
                    total_tokens=1500,
                    cost_usd=0.052500,
                    mode="short",
                    created_at=datetime.now(timezone.utc),
                ),
                LlmUsageEvent(
                    user_sub="alice",
                    kind="embedding",
                    provider="voyage",
                    model="voyage-3",
                    input_tokens=200,
                    output_tokens=0,
                    total_tokens=200,
                    cost_usd=0.000012,
                    tokens_estimated=True,
                    created_at=datetime.now(timezone.utc),
                ),
            ]
        )
        s.commit()

    body = admin.get("/admin/usage/overview?days=30").json()
    totals = body["totals"]
    # One chat call → requests == 1; tokens include the embedding.
    assert totals["requests"] == 1
    assert totals["input_tokens"] == 1200
    assert totals["output_tokens"] == 500
    assert totals["total_tokens"] == 1700
    assert totals["cost_usd"] == pytest.approx(0.052512, rel=1e-6)

    models = {r["label"] for r in body["by_model"]}
    assert models == {"claude-opus-4-7", "voyage-3"}

    users = {r["label"] for r in body["by_user"]}
    assert "alice@example.com" in users


def test_overview_days_out_of_range_is_rejected(session_factory, set_admins):
    set_admins("boss@example.com")
    admin = _make_client(session_factory, _user("boss-sub", "boss@example.com"))
    assert admin.get("/admin/usage/overview?days=0").status_code == 422
    assert admin.get("/admin/usage/overview?days=9999").status_code == 422
