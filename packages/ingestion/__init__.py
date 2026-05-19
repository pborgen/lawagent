"""Ingestion pipeline: turn raw legal documents into searchable chunks.

Chunking and file discovery live here. Persisting chunks to Postgres is
delegated to `store.write_chunks`. The agent reads via `store.similarity_search`.
"""

from ingestion.chunking import chunk_file, metadata_from_path
from ingestion.pipeline import discover_files, ingest

__all__ = [
    "chunk_file",
    "metadata_from_path",
    "discover_files",
    "ingest",
]
