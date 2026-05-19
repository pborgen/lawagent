from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from corpus import Chunk
from ingestion.chunking import chunk_file
from store import DEFAULT_COLLECTION, write_chunks


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


def ingest(
    source: Path,
    *,
    collection: str = DEFAULT_COLLECTION,
    connection: Optional[str] = None,
) -> tuple[list[Path], list[Chunk]]:
    """End-to-end: discover → chunk → embed → write.

    Returns the discovered files and the resulting chunks so callers
    (CLI, tests) can report on what happened.
    """
    files = discover_files(source)
    chunks = chunk_files(files)
    if chunks:
        write_chunks(chunks, collection=collection, connection=connection)
    return files, chunks
