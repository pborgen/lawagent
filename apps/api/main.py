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
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.src.graph import ask_with_sources
from api.auth import CurrentUser, log_auth_state
from api.files import router as files_router
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

# Every /files/* route requires a verified Cognito user. /health is
# intentionally open so App Runner's health check can hit it without a token.
app.include_router(files_router)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    mode: Mode = "short"


class ChatResponse(BaseModel):
    answer: str
    mode: Mode
    sources: list[Source] = []


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check — does not touch the LLM or the database."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, _user: CurrentUser) -> ChatResponse:
    """Answer one question with the grounded CT-divorce agent.

    Defined as a sync `def` on purpose: the agent call blocks on the LLM,
    and FastAPI runs sync routes in a worker thread, so a slow answer
    does not stall the event loop.
    """
    try:
        answer, sources = ask_with_sources(req.question, mode=req.mode)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the UI
        raise HTTPException(
            status_code=502,
            detail=f"The assistant failed to answer: {exc}",
        ) from exc

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
