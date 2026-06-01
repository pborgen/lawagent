"""Project CRUD — every route scoped to the authenticated owner.

A "project" is a container the user creates to organize the documents
and work for one matter (divorce case, custody motion, etc.). It owns
an S3 prefix (`projects/{project_id}/...`) and, later, its own slice of
the vector store.

Authorization model:
  - Every route depends on `require_db_user`, so the caller is always
    a known User row.
  - Listing and any single-project lookup filter by `owner_sub`; a 404
    is returned for projects that exist but belong to someone else so
    the existence of another user's project never leaks.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.users import CurrentDbUser
from db import Project, get_db_session


router = APIRouter(prefix="/projects", tags=["projects"])


# --- DTOs ---------------------------------------------------------------


class ProjectOut(BaseModel):
    """JSON shape returned to the UI. Hides the FK to keep the surface tight."""

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    matter_type: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_row(cls, row: Project) -> "ProjectOut":
        return cls(
            id=row.id,
            name=row.name,
            slug=row.slug,
            description=row.description,
            matter_type=row.matter_type,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    matter_type: str | None = Field(default=None, max_length=80)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    matter_type: str | None = Field(default=None, max_length=80)


class ProjectListResponse(BaseModel):
    items: list[ProjectOut]


# --- Helpers ------------------------------------------------------------


_SLUG_FALLBACK = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    """Best-effort URL slug; falls back to `project` if the input is empty
    once stripped (e.g. all-emoji name).
    """
    cleaned = _SLUG_FALLBACK.sub("-", text.lower()).strip("-")
    return cleaned or "project"


def _unique_slug(session: Session, owner_sub: str, base: str) -> str:
    """Append -2, -3, ... until the (owner_sub, slug) pair is free."""
    slug = base
    suffix = 2
    while session.scalar(
        select(Project.id).where(Project.owner_sub == owner_sub, Project.slug == slug)
    ):
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _load_owned_project(
    session: Session, project_id: uuid.UUID, owner_sub: str
) -> Project:
    """Fetch a project belonging to `owner_sub`, or raise 404."""
    project = session.get(Project, project_id)
    if project is None or project.owner_sub != owner_sub:
        # 404, not 403 — never reveal that another user has this UUID.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


# --- Routes -------------------------------------------------------------


@router.get("", response_model=ProjectListResponse)
def list_projects(
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectListResponse:
    rows = session.scalars(
        select(Project)
        .where(Project.owner_sub == user.cognito_sub)
        .order_by(Project.created_at.desc())
    ).all()
    return ProjectListResponse(items=[ProjectOut.from_orm_row(r) for r in rows])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectOut:
    base_slug = _slugify(payload.slug or payload.name)
    slug = _unique_slug(session, user.cognito_sub, base_slug)
    project = Project(
        owner_sub=user.cognito_sub,
        name=payload.name.strip(),
        slug=slug,
        description=payload.description,
        matter_type=payload.matter_type,
    )
    session.add(project)
    try:
        session.commit()
    except IntegrityError as exc:
        # Defense in depth — `_unique_slug` should have prevented this,
        # but two concurrent creates of the same slug could race.
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A project with this slug already exists.",
        ) from exc
    session.refresh(project)
    return ProjectOut.from_orm_row(project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectOut:
    return ProjectOut.from_orm_row(
        _load_owned_project(session, project_id, user.cognito_sub)
    )


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectOut:
    project = _load_owned_project(session, project_id, user.cognito_sub)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(project, field, value)
    # Manually bump updated_at — onupdate fires on SQL UPDATE, but only
    # when the model is actually flushed; setting it here ensures the
    # value the route returns matches what's in the DB even on no-op patches.
    project.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(project)
    return ProjectOut.from_orm_row(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Delete the metadata row.

    The S3 prefix under projects/{project_id}/ is NOT garbage-collected
    here — that's a separate sweep that runs asynchronously, so a
    half-finished S3 delete can't leave the DB in a wedged state.
    """
    project = _load_owned_project(session, project_id, user.cognito_sub)
    session.delete(project)
    session.commit()
