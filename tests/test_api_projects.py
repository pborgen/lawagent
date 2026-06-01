"""Tests for the /projects router and per-user ownership enforcement.

We swap in a SQLite in-memory engine so the suite stays offline. The
auth dependency is overridden to return a chosen `AuthUser` per test so
we can simulate two users hitting the same router.

The critical property we're guarding is: a project belonging to user A
must be invisible (404) to user B — never 403, since 403 would leak
that the UUID exists.
"""
from __future__ import annotations

import uuid
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import AuthUser, require_user
from api.projects import router as projects_router
from db.models import Base
from db.session import get_db_session


@pytest.fixture()
def engine():
    """Fresh in-memory SQLite + schema for each test.

    StaticPool keeps a single shared connection alive for the duration
    of the test, so every Session sees the same `:memory:` database.
    Without this, each new connection would get its own empty DB and
    the foreign key from projects → users would never resolve.
    """
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


def _make_client(session_factory, auth_user: AuthUser) -> TestClient:
    app = FastAPI()
    app.include_router(projects_router)

    def _override_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def _override_auth() -> AuthUser:
        return auth_user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[require_user] = _override_auth
    return TestClient(app)


def _make_user(sub: str, email: str) -> AuthUser:
    return AuthUser(sub=sub, email=email, claims={"sub": sub, "email": email})


# --- Tests --------------------------------------------------------------


def test_create_and_list_returns_only_own_projects(session_factory):
    alice = _make_user("alice-sub", "alice@example.com")
    bob = _make_user("bob-sub", "bob@example.com")

    alice_client = _make_client(session_factory, alice)
    bob_client = _make_client(session_factory, bob)

    r = alice_client.post("/projects", json={"name": "Alice Case"})
    assert r.status_code == 201
    a_id = r.json()["id"]

    r = bob_client.post("/projects", json={"name": "Bob Case"})
    assert r.status_code == 201
    b_id = r.json()["id"]
    assert a_id != b_id

    a_list = alice_client.get("/projects").json()["items"]
    assert [p["id"] for p in a_list] == [a_id]

    b_list = bob_client.get("/projects").json()["items"]
    assert [p["id"] for p in b_list] == [b_id]


def test_create_generates_unique_slug_per_owner(session_factory):
    alice = _make_user("alice-sub", "alice@example.com")
    client = _make_client(session_factory, alice)

    r1 = client.post("/projects", json={"name": "Smith v. Smith"})
    r2 = client.post("/projects", json={"name": "Smith v. Smith"})
    assert r1.status_code == 201 and r2.status_code == 201
    s1, s2 = r1.json()["slug"], r2.json()["slug"]
    assert s1 == "smith-v-smith"
    assert s2 == "smith-v-smith-2"


def test_same_slug_allowed_for_different_owners(session_factory):
    alice = _make_user("alice-sub", "alice@example.com")
    bob = _make_user("bob-sub", "bob@example.com")
    a_client = _make_client(session_factory, alice)
    b_client = _make_client(session_factory, bob)

    a = a_client.post("/projects", json={"name": "Estate"}).json()
    b = b_client.post("/projects", json={"name": "Estate"}).json()
    # Different owners → same slug is fine; uniqueness is per-owner.
    assert a["slug"] == "estate"
    assert b["slug"] == "estate"


def test_cross_user_get_returns_404_not_403(session_factory):
    """Existence of another user's project must not leak via 403."""
    alice = _make_user("alice-sub", "alice@example.com")
    bob = _make_user("bob-sub", "bob@example.com")
    a_client = _make_client(session_factory, alice)
    b_client = _make_client(session_factory, bob)

    alice_project = a_client.post("/projects", json={"name": "Private"}).json()
    r = b_client.get(f"/projects/{alice_project['id']}")
    assert r.status_code == 404


def test_cross_user_patch_returns_404(session_factory):
    alice = _make_user("alice-sub", "alice@example.com")
    bob = _make_user("bob-sub", "bob@example.com")
    a_client = _make_client(session_factory, alice)
    b_client = _make_client(session_factory, bob)

    p = a_client.post("/projects", json={"name": "Untouched"}).json()
    r = b_client.patch(f"/projects/{p['id']}", json={"name": "Hijacked"})
    assert r.status_code == 404

    # Confirm the project still has its original name on Alice's side.
    again = a_client.get(f"/projects/{p['id']}").json()
    assert again["name"] == "Untouched"


def test_cross_user_delete_returns_404(session_factory):
    alice = _make_user("alice-sub", "alice@example.com")
    bob = _make_user("bob-sub", "bob@example.com")
    a_client = _make_client(session_factory, alice)
    b_client = _make_client(session_factory, bob)

    p = a_client.post("/projects", json={"name": "Keep"}).json()
    r = b_client.delete(f"/projects/{p['id']}")
    assert r.status_code == 404

    # Still exists for Alice.
    assert a_client.get(f"/projects/{p['id']}").status_code == 200


def test_unknown_uuid_returns_404(session_factory):
    alice = _make_user("alice-sub", "alice@example.com")
    client = _make_client(session_factory, alice)
    r = client.get(f"/projects/{uuid.uuid4()}")
    assert r.status_code == 404


def test_patch_updates_fields(session_factory):
    alice = _make_user("alice-sub", "alice@example.com")
    client = _make_client(session_factory, alice)
    p = client.post("/projects", json={"name": "Original"}).json()
    r = client.patch(
        f"/projects/{p['id']}",
        json={"name": "Renamed", "description": "New desc"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Renamed"
    assert body["description"] == "New desc"


def test_delete_removes_project(session_factory):
    alice = _make_user("alice-sub", "alice@example.com")
    client = _make_client(session_factory, alice)
    p = client.post("/projects", json={"name": "Disposable"}).json()
    r = client.delete(f"/projects/{p['id']}")
    assert r.status_code == 204
    assert client.get(f"/projects/{p['id']}").status_code == 404
