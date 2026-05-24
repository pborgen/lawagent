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

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.src.graph import ask_with_sources
from api.files import router as files_router


Mode = Literal["short", "memo", "annotate"]


class Source(BaseModel):
    """One retrieved passage, surfaced to the UI as a clickable citation.

    Pulled straight from chunk metadata, so `url` is never something the
    LLM produced.
    """

    citation: str
    url: str = ""
    source_type: str = ""


app = FastAPI(
    title="lawagent API",
    description=(
        "Connecticut divorce research assistant — grounded, "
        "citation-backed answers. Not legal advice."
    ),
    version="0.1.0",
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
def chat(req: ChatRequest) -> ChatResponse:
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
