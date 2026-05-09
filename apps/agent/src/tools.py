from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.tools import tool

from llm import get_embeddings


_VECTORSTORE: Optional[Chroma] = None


def _get_vectorstore() -> Chroma:
    global _VECTORSTORE
    if _VECTORSTORE is None:
        persist = Path(os.getenv("LAWAGENT_VECTORSTORE_DIR", "./data/vectorstore"))
        _VECTORSTORE = Chroma(
            collection_name="ct-divorce",
            embedding_function=get_embeddings(),
            persist_directory=str(persist),
        )
    return _VECTORSTORE


@tool
def retrieve(query: str, k: int = 6, source_type: Optional[str] = None) -> str:
    """Search the CT divorce corpus and return passages that may answer the query.

    Args:
        query: A natural-language search query.
        k: Number of passages to return (default 6).
        source_type: Optionally filter to one of 'statute', 'practice_book',
            'case', or 'case_file'.

    Returns:
        A formatted list of passages, each with its citation and source path.
        Use these passages — and only these passages — to ground your answer.
    """
    vs = _get_vectorstore()
    filter_ = {"source_type": source_type} if source_type else None
    docs = vs.similarity_search(query, k=k, filter=filter_)

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
