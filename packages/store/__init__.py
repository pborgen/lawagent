"""Postgres + pgvector access — single entry point for the whole monorepo.

All reads and writes to the vector store go through this package.
Ingestion orchestrates chunking then calls `write_chunks`; the agent
calls `similarity_search`. Nothing else should import `langchain_postgres`
or construct a `PGVector` directly.
"""

from store.pgvector import (
    DEFAULT_COLLECTION,
    delete_collection,
    get_vectorstore,
    resolve_connection,
    similarity_search,
    write_chunks,
)

__all__ = [
    "DEFAULT_COLLECTION",
    "delete_collection",
    "get_vectorstore",
    "resolve_connection",
    "similarity_search",
    "write_chunks",
]
