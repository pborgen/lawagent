from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool
from langchain_postgres import PGVector

from ingestion import get_vectorstore


_VECTORSTORE: Optional[PGVector] = None


def _vs() -> PGVector:
    global _VECTORSTORE
    if _VECTORSTORE is None:
        _VECTORSTORE = get_vectorstore()
    return _VECTORSTORE


@tool
def retrieve(query: str, k: int = 6, source_type: Optional[str] = None) -> str:
    """Search the CT divorce corpus and return passages that may answer the query.

    Args:
        query: A natural-language search query.
        k: Number of passages to return (default 6).
        source_type: Optionally filter to a corpus source type such as
            'statute', 'practice_book', 'case', 'court_form',
            'court_guide', 'law_library_guide', or 'case_file'.

    Returns:
        A formatted list of passages, each with its citation and source path.
        Use these passages — and only these passages — to ground your answer.
    """
    filter_ = {"source_type": source_type} if source_type else None
    docs = _vs().similarity_search(query, k=k, filter=filter_)

    if not docs:
        return "No passages found in the corpus for that query."

    out = []
    for i, d in enumerate(docs, start=1):
        meta = d.metadata or {}
        citation = meta.get("citation") or "(uncited)"
        stype = meta.get("source_type") or "?"
        out.append(
            f"[{i}] {citation}  ({stype})\n{d.page_content}\n"
        )
    return "\n---\n".join(out)
