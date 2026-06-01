"""Tests for the /files convert endpoint.

Offline: in-memory SQLite for the DB (same harness as test_api_projects),
moto for S3, and PyMuPDF to synthesize PDFs. The project is created via
the real /projects route so the user-row upsert and FK are exercised
rather than hand-seeded.
"""
from __future__ import annotations

import uuid
from typing import Iterator

import boto3
import fitz  # PyMuPDF
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import AuthUser, require_user
from api.files import router as files_router
from api.projects import router as projects_router
from db.models import Base
from db.session import get_db_session
from settings import get_settings

BUCKET = "test-bucket"


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
def s3_env(monkeypatch):
    """Point the service at a moto-backed bucket for the duration of a test."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("LAWAGENT_S3_URI", f"s3://{BUCKET}")
    get_settings.cache_clear()
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client
    get_settings.cache_clear()


def _make_client(session_factory, auth_user: AuthUser) -> TestClient:
    app = FastAPI()
    app.include_router(projects_router)
    app.include_router(files_router)

    def _override_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[require_user] = lambda: auth_user
    return TestClient(app)


def _user(sub: str = "alice-sub", email: str = "alice@example.com") -> AuthUser:
    return AuthUser(sub=sub, email=email, claims={"sub": sub, "email": email})


def _pdf_bytes(text: str | None) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _new_project(client: TestClient) -> str:
    r = client.post("/projects", json={"name": "Smith v. Smith"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_convert_pdf_writes_docx_into_project(session_factory, s3_env):
    client = _make_client(session_factory, _user())
    pid = _new_project(client)
    key = f"projects/{pid}/discovery/affidavit.pdf"
    s3_env.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=_pdf_bytes("Net weekly income from all sources reported below."),
    )

    r = client.post("/files/convert", json={"project_id": pid, "key": key})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["key"] == f"projects/{pid}/discovery/affidavit.docx"
    assert body["name"] == "discovery/affidavit.docx"
    assert body["scanned"] is False

    # The .docx now exists in the bucket with the Word content type.
    head = s3_env.head_object(Bucket=BUCKET, Key=body["key"])
    assert "wordprocessingml" in head["ContentType"]


def test_convert_flags_scanned_pdf(session_factory, s3_env):
    client = _make_client(session_factory, _user())
    pid = _new_project(client)
    key = f"projects/{pid}/scan.pdf"
    s3_env.put_object(Bucket=BUCKET, Key=key, Body=_pdf_bytes(None))  # no text layer

    r = client.post("/files/convert", json={"project_id": pid, "key": key})
    assert r.status_code == 200, r.text
    assert r.json()["scanned"] is True


def test_convert_rejects_non_pdf(session_factory, s3_env):
    client = _make_client(session_factory, _user())
    pid = _new_project(client)
    key = f"projects/{pid}/notes.txt"
    r = client.post("/files/convert", json={"project_id": pid, "key": key})
    assert r.status_code == 400


def test_convert_rejects_key_outside_project(session_factory, s3_env):
    client = _make_client(session_factory, _user())
    pid = _new_project(client)
    # A key under a different project id must be refused even though the
    # caller owns `pid`.
    foreign = f"projects/{uuid.uuid4()}/secret.pdf"
    r = client.post("/files/convert", json={"project_id": pid, "key": foreign})
    assert r.status_code == 403


def test_convert_on_unowned_project_returns_404(session_factory, s3_env):
    alice = _make_client(session_factory, _user())
    pid = _new_project(alice)
    key = f"projects/{pid}/doc.pdf"

    bob = _make_client(session_factory, _user("bob-sub", "bob@example.com"))
    r = bob.post("/files/convert", json={"project_id": pid, "key": key})
    assert r.status_code == 404
