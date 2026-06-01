from __future__ import annotations

from contextvars import ContextVar
from typing import Optional, TypedDict

from langchain_core.tools import tool

from store import collection_for, similarity_search


class RetrievedSource(TypedDict):
    """Lightweight record of one chunk the `retrieve` tool surfaced.

    Used by the chat surface to render a "Sources" panel — these come
    straight from chunk metadata, so the URL is never something the LLM
    made up.
    """

    citation: str
    url: str
    source_type: str


# Per-request collector. `ask()` in graph.py sets this before invoking the
# agent and reads it after — so every chunk the `retrieve` tool returns is
# captured for the API to surface as clickable sources.
#
# A ContextVar (not a module-level list) so concurrent requests in
# FastAPI's threadpool don't share each other's recorders.
RETRIEVAL_RECORDER: ContextVar[Optional[list[RetrievedSource]]] = ContextVar(
    "retrieval_recorder", default=None
)

# Which state's collection the retrieve tool reads from. Set by `ask()` from
# the request's jurisdiction (a state slug like "ny"); `None` → Connecticut.
# A ContextVar — not a tool argument — so the *caller* picks the jurisdiction,
# never the LLM, and concurrent requests don't cross collections.
RETRIEVAL_STATE: ContextVar[Optional[str]] = ContextVar(
    "retrieval_state", default=None
)


@tool
def retrieve(query: str, k: int = 6, source_type: Optional[str] = None) -> str:
    """Search the active jurisdiction's legal corpus for passages answering the query.

    Args:
        query: A natural-language search query.
        k: Number of passages to return (default 6).
        source_type: Optionally filter to a corpus source type such as
            'statute', 'practice_book', 'case', 'court_form',
            'court_guide', 'law_library_guide', or 'case_file'.

    Returns:
        A formatted list of passages, each with its citation, source path,
        and (when available) the URL of the official upstream source.
        Use these passages — and only these passages — to ground your answer.
        When you cite a passage and a URL was shown next to it, render the
        citation as a markdown link: `[citation](url)`. Never invent URLs.
    """
    filter_ = {"source_type": source_type} if source_type else None
    collection = collection_for(RETRIEVAL_STATE.get())
    docs = similarity_search(query, k=k, collection=collection, filter=filter_)

    if not docs:
        return "No passages found in the corpus for that query."

    recorder = RETRIEVAL_RECORDER.get()

    out = []
    for i, d in enumerate(docs, start=1):
        meta = d.metadata or {}
        citation = meta.get("citation") or "(uncited)"
        stype = meta.get("source_type") or "?"
        source_url = meta.get("source_url") or ""

        # Record for the sources panel (only if we're inside an ask() call).
        if recorder is not None and citation:
            recorder.append(
                RetrievedSource(
                    citation=citation, url=source_url, source_type=stype
                )
            )

        # Show URL to the LLM so it can produce `[citation](url)` markdown.
        url_line = f"\nURL: {source_url}" if source_url else ""
        out.append(
            f"[{i}] {citation}  ({stype}){url_line}\n{d.page_content}\n"
        )
    return "\n---\n".join(out)
