from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from langchain_chroma import Chroma

from corpus import Chunk
from ingestion.chunking import chunk_file
from llm import get_embeddings


DEFAULT_COLLECTION = "ct-divorce"
SUPPORTED_SUFFIXES = {".txt", ".md"}


def discover_files(source: Path) -> list[Path]:
    """Return all .txt/.md files under `source` (or `source` itself if it's a file)."""
    if source.is_file():
        return [source]
    return sorted(
        p
        for p in source.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )


def chunk_files(files: Iterable[Path]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for f in files:
        chunks.extend(chunk_file(f))
    return chunks


def _resolve_persist_dir(persist_dir: Optional[Path]) -> Path:
    return persist_dir or Path(
        os.getenv("LAWAGENT_VECTORSTORE_DIR", "./data/vectorstore")
    )


def write_to_chroma(
    chunks: list[Chunk],
    *,
    collection: str = DEFAULT_COLLECTION,
    persist_dir: Optional[Path] = None,
) -> None:
    persist = _resolve_persist_dir(persist_dir)
    persist.mkdir(parents=True, exist_ok=True)

    vectorstore = Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=str(persist),
    )
    vectorstore.add_texts(
        texts=[c.text for c in chunks],
        metadatas=[c.to_chroma_metadata() for c in chunks],
        ids=[c.id for c in chunks],
    )


def ingest(
    source: Path,
    *,
    collection: str = DEFAULT_COLLECTION,
    persist_dir: Optional[Path] = None,
) -> tuple[list[Path], list[Chunk]]:
    """End-to-end: discover → chunk → embed → write.

    Returns the discovered files and the resulting chunks so callers
    (CLI, tests) can report on what happened.
    """
    files = discover_files(source)
    chunks = chunk_files(files)
    if chunks:
        write_to_chroma(chunks, collection=collection, persist_dir=persist_dir)
    return files, chunks
