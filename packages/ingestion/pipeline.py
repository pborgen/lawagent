from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from langchain_postgres import PGVector

from corpus import Chunk
from ingestion.chunking import chunk_file
from llm import get_embeddings
from settings import get_settings


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


def _resolve_connection(connection: Optional[str]) -> str:
    return connection or get_settings().require_pg_url()


def get_vectorstore(
    *,
    collection: str = DEFAULT_COLLECTION,
    connection: Optional[str] = None,
) -> PGVector:
    """Return a PGVector handle for the given collection.

    Assumes the `vector` extension is already enabled on the target database
    (see docker-compose.yml for local dev).
    """
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=collection,
        connection=_resolve_connection(connection),
        use_jsonb=True,
    )


def write_to_vectorstore(
    chunks: list[Chunk],
    *,
    collection: str = DEFAULT_COLLECTION,
    connection: Optional[str] = None,
) -> None:
    vectorstore = get_vectorstore(collection=collection, connection=connection)
    vectorstore.add_texts(
        texts=[c.text for c in chunks],
        metadatas=[c.to_metadata_dict() for c in chunks],
        ids=[c.id for c in chunks],
    )


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
        write_to_vectorstore(chunks, collection=collection, connection=connection)
    return files, chunks
