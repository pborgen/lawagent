"""FastAPI wrapper around `agent.src.graph.ask()`.

This is the single bridge between the TypeScript frontend and the Python
agent. The frontend never queries pgvector or the LLM directly — it
POSTs a question here, and this service runs the same grounded,
citation-backed agent the CLI uses.

Run it:
    uvicorn api.main:app --reload --port 8000
    # or, after `uv sync`:
    lawagent-api
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator, Literal, Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agent.src.graph import ask_with_sources
from api.admin import router as admin_router
from api.auth import log_auth_state
from api.files import router as files_router
from api.projects import router as projects_router
from api.users import CurrentDbUser
from api.users import router as users_router
from db import Project, bootstrap_schema, get_db_session, record_usage_events
from llm import record_usage
from settings import get_settings


logger = logging.getLogger(__name__)


Mode = Literal["short", "memo", "annotate"]


class Source(BaseModel):
    """One retrieved passage, surfaced to the UI as a clickable citation.

    Pulled straight from chunk metadata, so `url` is never something the
    LLM produced.
    """

    citation: str
    url: str = ""
    source_type: str = ""


def _verify_s3_connection() -> None:
    """Confirm the configured S3 bucket is reachable, or raise.

    Runs once at startup so misconfigured credentials, a wrong bucket
    name, or a bad region surface immediately instead of waiting for the
    first /files request to fail.
    """
    uri = get_settings().s3_uri
    if not uri:
        raise RuntimeError(
            "LAWAGENT_S3_URI is not set. The API needs an s3://bucket/prefix/ "
            "to manage case files."
        )
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise RuntimeError(f"LAWAGENT_S3_URI is not a valid s3:// URI: {uri!r}")
    bucket = parsed.netloc
    client = boto3.client("s3", config=Config(signature_version="s3v4"))
    try:
        client.head_bucket(Bucket=bucket)
    except NoCredentialsError as exc:
        raise RuntimeError(
            "No AWS credentials found. Configure with `aws configure`, env "
            "vars, or an instance profile."
        ) from exc
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        raise RuntimeError(
            f"Could not reach s3://{bucket}/ ({code}): {exc}"
        ) from exc
    except BotoCoreError as exc:
        raise RuntimeError(f"S3 connection failed: {exc}") from exc
    logger.info("S3 connection verified: s3://%s/", bucket)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    _verify_s3_connection()
    # Create app-data tables (users, projects) if they don't exist yet.
    # No-op once they're there; safe to call on every cold start.
    bootstrap_schema()
    log_auth_state(get_settings())
    yield


app = FastAPI(
    title="lawagent API",
    description=(
        "Connecticut divorce research assistant — grounded, "
        "citation-backed answers. Not legal advice."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# The Next.js app proxies through its own server route (`/api/chat`), so
# browser CORS is not strictly required. Allowing localhost dev origins
# anyway lets you hit this API directly (curl, Swagger UI) while developing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)

# Every /files/* and /projects/* route requires a verified Cognito user.
# /health is intentionally open so App Runner's health check can hit it
# without a token.
app.include_router(files_router)
app.include_router(projects_router)
app.include_router(users_router)
app.include_router(admin_router)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    mode: Mode = "short"
    # Optional: attribute this question's usage to a project. The web app
    # forwards the active-project cookie; omitted from direct API calls.
    project_id: Optional[uuid.UUID] = None


class ChatResponse(BaseModel):
    answer: str
    mode: Mode
    sources: list[Source] = []


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check — does not touch the LLM or the database."""
    return {"status": "ok"}


def _resolve_owned_project_id(
    session: Session, project_id: Optional[uuid.UUID], owner_sub: str
) -> Optional[uuid.UUID]:
    """Return `project_id` only if the caller owns it; else None.

    Usage attribution must never become a way to probe another user's
    project IDs, and a stale active-project cookie shouldn't 500 a chat —
    so an unknown or unowned project just attributes the usage to no
    project rather than raising.
    """
    if project_id is None:
        return None
    project = session.get(Project, project_id)
    if project is None or project.owner_sub != owner_sub:
        return None
    return project_id


@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    user: CurrentDbUser,
    session: Annotated[Session, Depends(get_db_session)],
) -> ChatResponse:
    """Answer one question with the grounded CT-divorce agent.

    Defined as a sync `def` on purpose: the agent call blocks on the LLM,
    and FastAPI runs sync routes in a worker thread, so a slow answer
    does not stall the event loop.

    LLM token usage is metered (`record_usage`) and persisted per user.
    Persistence is best-effort: a metering failure is logged but never
    fails the chat.
    """
    try:
        with record_usage() as events:
            answer, sources = ask_with_sources(req.question, mode=req.mode)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the UI
        raise HTTPException(
            status_code=502,
            detail=f"The assistant failed to answer: {exc}",
        ) from exc

    try:
        project_id = _resolve_owned_project_id(
            session, req.project_id, user.cognito_sub
        )
        record_usage_events(
            session,
            events=events,
            user_sub=user.cognito_sub,
            project_id=project_id,
            mode=req.mode,
        )
    except Exception:  # noqa: BLE001 - metering must not break the answer
        logger.exception("Failed to persist LLM usage for %s", user.cognito_sub)

    return ChatResponse(
        answer=answer,
        mode=req.mode,
        sources=[Source(**s) for s in sources],
    )


def main() -> None:
    """Entry point for the `lawagent-api` console script."""
    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
