"""Cognito JWT verification, used as a FastAPI dependency on every route.

Trust model:
    Browser ─► Next.js ─► FastAPI
                  │           │
                  │           └─ verifies ID-token JWT here, against
                  │              the Cognito user pool's JWKS, on
                  │              every request.
                  │
                  └─ stores ID + refresh tokens in an httpOnly session
                     cookie; attaches `Authorization: Bearer <id_token>`
                     when forwarding to FastAPI.

The FastAPI service is the secured boundary — even if someone curls it
directly (App Runner gives it a public URL), they need a valid Cognito
ID token whose email is in COGNITO_ALLOWED_EMAILS.

Debug bypass:
    Setting LAWAGENT_AUTH_DISABLED=true skips verification entirely and
    returns a synthetic "dev" user. Intended for local dev only — the
    App Runner runtime env never sets it.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient

from settings import Settings, get_settings


logger = logging.getLogger(__name__)


# Synthetic user returned in the AUTH_DISABLED dev path. Routes that
# need an email read `.email`; that's the only field they ever touch.
class AuthUser:
    __slots__ = ("sub", "email", "claims")

    def __init__(self, sub: str, email: str, claims: dict) -> None:
        self.sub = sub
        self.email = email
        self.claims = claims

    @classmethod
    def dev(cls) -> "AuthUser":
        return cls(sub="dev", email="dev@localhost", claims={"dev": True})


@lru_cache(maxsize=1)
def _jwks_client_for(region: str, user_pool_id: str) -> PyJWKClient:
    """Build (and memoize) one JWKS client per (region, pool).

    PyJWKClient itself caches signing keys after the first fetch, so
    re-using this single instance avoids hitting Cognito on every
    request.
    """
    jwks_uri = (
        f"https://cognito-idp.{region}.amazonaws.com/"
        f"{user_pool_id}/.well-known/jwks.json"
    )
    return PyJWKClient(jwks_uri, cache_keys=True, lifespan=3600)


def _extract_bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def _verify_id_token(token: str, settings: Settings) -> dict:
    """Verify signature, issuer, audience, expiry. Returns claims."""
    region, pool_id, client_id = settings.require_cognito()
    jwks_client = _jwks_client_for(region, pool_id)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=f"https://cognito-idp.{region}.amazonaws.com/{pool_id}",
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.PyJWTError as exc:
        # Log the underlying reason; never leak it to the client.
        logger.warning("JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthUser:
    """FastAPI dependency: returns the verified caller, or 401/403.

    Steps:
      1. If LAWAGENT_AUTH_DISABLED, return a dev user without checking.
      2. Extract the Bearer token from the Authorization header.
      3. Verify the JWT against the Cognito user pool's JWKS.
      4. Enforce the email allowlist (COGNITO_ALLOWED_EMAILS).
    """
    if settings.auth_disabled:
        return AuthUser.dev()

    token = _extract_bearer(request)
    claims = _verify_id_token(token, settings)

    email = (claims.get("email") or "").strip().lower()
    if not claims.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified.",
        )

    allowed = settings.allowed_email_set()
    if not allowed:
        # Fail closed: an empty allowlist means nobody is allowed in.
        # Reaching this in prod means COGNITO_ALLOWED_EMAILS was forgotten.
        logger.error("COGNITO_ALLOWED_EMAILS is empty; rejecting %s", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access not configured.",
        )
    if email not in allowed:
        logger.warning("rejected sign-in attempt from %s", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not authorized.",
        )

    return AuthUser(sub=claims["sub"], email=email, claims=claims)


CurrentUser = Annotated[AuthUser, Depends(require_user)]


def log_auth_state(settings: Settings) -> None:
    """Single line at startup so the operator can see which mode is live."""
    if settings.auth_disabled:
        logger.warning(
            "AUTH DISABLED — LAWAGENT_AUTH_DISABLED is set. "
            "All requests bypass JWT verification. Dev use only."
        )
        return
    region, pool_id, client_id = settings.require_cognito()
    allowed = ", ".join(sorted(settings.allowed_email_set())) or "<empty>"
    logger.info(
        "Auth: Cognito JWT required (pool=%s, client=%s, allowed=%s)",
        pool_id,
        client_id,
        allowed,
    )
