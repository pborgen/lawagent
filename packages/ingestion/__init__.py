"""Ingestion pipeline: turn raw legal documents into a searchable pgvector store.

This package is the only place that knows how to build the corpus.
The agent app does NOT import from here — it just reads from Postgres
through `ingestion.pipeline.get_vectorstore()` / `llm.get_embeddings()`.
"""

from ingestion.chunking import chunk_file, metadata_from_path
from ingestion.pipeline import (
    discover_files,
    get_vectorstore,
    ingest,
    write_to_vectorstore,
)

__all__ = [
    "chunk_file",
    "metadata_from_path",
    "discover_files",
    "get_vectorstore",
    "ingest",
    "write_to_vectorstore",
]
