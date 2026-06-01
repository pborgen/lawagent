"""DB-backed current-user dependency.

`require_user` (in auth.py) is the security boundary: it verifies the
Cognito JWT and returns a typed `AuthUser`. Once we trust the caller,
this module materializes them as a row in `lawagent_users` so the
projects table has a valid foreign key to point at.

Routes that only need *who's calling* (chat, presign URLs that don't
write metadata) can keep using `CurrentUser` from auth.py — no DB hit.
Routes that own data (projects, file-metadata, anything we'll attach
to a user later) take `CurrentDbUser` from here and get the live ORM
instance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import AuthUser, require_user
from db import User, get_db_session
from settings import get_settings


def _is_admin_email(email: str) -> bool:
    """Whether this email is configured as an admin (LAWAGENT_ADMIN_EMAILS)."""
    return email.strip().lower() in get_settings().admin_email_set()


def _upsert_user(session: Session, auth_user: AuthUser) -> User:
    """Find-or-create the User row for this caller, refreshing last_seen_at.

    Admin status is re-derived from the env allowlist on every login, so
    granting or revoking admin is just an env change that takes effect on
    the user's next request — never a manual DB edit.
    """
    admin = _is_admin_email(auth_user.email)
    existing = session.get(User, auth_user.sub)
    if existing is None:
        user = User(
            cognito_sub=auth_user.sub,
            email=auth_user.email,
            display_name=(auth_user.claims.get("name") or auth_user.email.split("@")[0])
            if isinstance(auth_user.claims, dict)
            else None,
            is_admin=admin,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    # Email can change in Cognito (rare, but verified email updates do
    # happen) — keep our copy in sync so the UI shows the right address.
    changed = False
    if existing.email != auth_user.email:
        existing.email = auth_user.email
        changed = True
    if existing.is_admin != admin:
        existing.is_admin = admin
        changed = True
    existing.last_seen_at = datetime.now(timezone.utc)
    session.commit()
    if changed:
        session.refresh(existing)
    return existing


def require_db_user(
    auth_user: Annotated[AuthUser, Depends(require_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> User:
    """FastAPI dependency: verified caller, materialized as a User row."""
    return _upsert_user(session, auth_user)


CurrentDbUser = Annotated[User, Depends(require_db_user)]


def require_admin(user: CurrentDbUser) -> User:
    """FastAPI dependency: the caller, required to be an admin (else 403)."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]


# --- /me ----------------------------------------------------------------

router = APIRouter(tags=["users"])


class MeResponse(BaseModel):
    """Identity the web app uses to gate the admin UI."""

    sub: str
    email: str
    is_admin: bool


@router.get("/me", response_model=MeResponse)
def me(user: CurrentDbUser) -> MeResponse:
    """Return the authenticated user's identity and admin flag."""
    return MeResponse(sub=user.cognito_sub, email=user.email, is_admin=user.is_admin)
