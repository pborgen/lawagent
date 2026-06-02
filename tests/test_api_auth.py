"""Unit tests for the FastAPI auth dependency.

We deliberately avoid talking to Cognito here — `_verify_id_token` is
monkeypatched to return canned claims. That keeps the test offline and
fast while still exercising the dependency's branching: AUTH_DISABLED
bypass, missing header, unverified email, email allowlist.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import auth as auth_mod
from api.auth import AuthUser, require_user
from settings import Settings, get_settings


def _make_client(settings: Settings) -> TestClient:
    app = FastAPI()

    def _override() -> Settings:
        return settings

    @app.get("/whoami")
    def whoami(user: AuthUser = Depends(require_user)) -> dict:
        return {"email": user.email, "sub": user.sub}

    app.dependency_overrides[get_settings] = _override
    return TestClient(app)


def test_auth_disabled_returns_dev_user():
    settings = Settings(LAWAGENT_AUTH_DISABLED="true")  # type: ignore[call-arg]
    client = _make_client(settings)
    r = client.get("/whoami")
    assert r.status_code == 200
    assert r.json() == {"email": "dev@localhost", "sub": "dev"}


def test_missing_bearer_returns_401():
    settings = Settings(  # type: ignore[call-arg]
        COGNITO_REGION="us-east-1",
        COGNITO_USER_POOL_ID="us-east-1_test",
        COGNITO_CLIENT_ID="testclient",
        COGNITO_ALLOWED_EMAILS="ok@example.com",
    )
    client = _make_client(settings)
    r = client.get("/whoami")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


def test_allowlisted_email_passes(monkeypatch):
    settings = Settings(  # type: ignore[call-arg]
        COGNITO_REGION="us-east-1",
        COGNITO_USER_POOL_ID="us-east-1_test",
        COGNITO_CLIENT_ID="testclient",
        COGNITO_ALLOWED_EMAILS="OK@example.com",
    )
    monkeypatch.setattr(
        auth_mod,
        "_verify_id_token",
        lambda token, _settings: {
            "sub": "abc123",
            "email": "ok@example.com",
            "email_verified": True,
        },
    )
    client = _make_client(settings)
    r = client.get("/whoami", headers={"Authorization": "Bearer faketoken"})
    assert r.status_code == 200
    assert r.json() == {"email": "ok@example.com", "sub": "abc123"}


def test_email_not_in_allowlist_returns_403(monkeypatch):
    settings = Settings(  # type: ignore[call-arg]
        COGNITO_REGION="us-east-1",
        COGNITO_USER_POOL_ID="us-east-1_test",
        COGNITO_CLIENT_ID="testclient",
        COGNITO_ALLOWED_EMAILS="ok@example.com",
    )
    monkeypatch.setattr(
        auth_mod,
        "_verify_id_token",
        lambda token, _settings: {
            "sub": "abc123",
            "email": "intruder@example.com",
            "email_verified": True,
        },
    )
    client = _make_client(settings)
    r = client.get("/whoami", headers={"Authorization": "Bearer faketoken"})
    assert r.status_code == 403


def test_unverified_email_returns_403(monkeypatch):
    settings = Settings(  # type: ignore[call-arg]
        COGNITO_REGION="us-east-1",
        COGNITO_USER_POOL_ID="us-east-1_test",
        COGNITO_CLIENT_ID="testclient",
        COGNITO_ALLOWED_EMAILS="ok@example.com",
    )
    monkeypatch.setattr(
        auth_mod,
        "_verify_id_token",
        lambda token, _settings: {
            "sub": "abc123",
            "email": "ok@example.com",
            "email_verified": False,
        },
    )
    client = _make_client(settings)
    r = client.get("/whoami", headers={"Authorization": "Bearer faketoken"})
    assert r.status_code == 403


def test_cognito_audiences_defaults_to_web_client():
    """With no extra audiences, the accepted set is just the web client id —
    identical to the previous single-audience behavior (backward compatible)."""
    settings = Settings(  # type: ignore[call-arg]
        COGNITO_REGION="us-east-1",
        COGNITO_USER_POOL_ID="us-east-1_test",
        COGNITO_CLIENT_ID="webclient",
    )
    assert settings.cognito_audiences() == ["webclient"]


def test_cognito_audiences_includes_extra_clients():
    """The native mobile client id (and any others) are admitted alongside web."""
    settings = Settings(  # type: ignore[call-arg]
        COGNITO_REGION="us-east-1",
        COGNITO_USER_POOL_ID="us-east-1_test",
        COGNITO_CLIENT_ID="webclient",
        COGNITO_EXTRA_AUDIENCES="mobileclient, otherclient",
    )
    assert settings.cognito_audiences() == [
        "webclient",
        "mobileclient",
        "otherclient",
    ]


def test_empty_allowlist_rejects_everyone(monkeypatch):
    """Fail-closed: forgetting to set COGNITO_ALLOWED_EMAILS must reject all callers."""
    settings = Settings(  # type: ignore[call-arg]
        COGNITO_REGION="us-east-1",
        COGNITO_USER_POOL_ID="us-east-1_test",
        COGNITO_CLIENT_ID="testclient",
        COGNITO_ALLOWED_EMAILS="",
    )
    monkeypatch.setattr(
        auth_mod,
        "_verify_id_token",
        lambda token, _settings: {
            "sub": "abc123",
            "email": "ok@example.com",
            "email_verified": True,
        },
    )
    client = _make_client(settings)
    r = client.get("/whoami", headers={"Authorization": "Bearer faketoken"})
    assert r.status_code == 403
