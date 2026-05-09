"""Ingestion pipeline: turn raw legal documents into a searchable Chroma store.

This package is the only place that knows how to build the corpus.
The agent app does NOT import from here — it just reads from Chroma
through `llm.get_embeddings()`.
"""

from ingestion.chunking import chunk_file, metadata_from_path
from ingestion.pipeline import discover_files, ingest, write_to_chroma

__all__ = [
    "chunk_file",
    "metadata_from_path",
    "discover_files",
    "ingest",
    "write_to_chroma",
]
