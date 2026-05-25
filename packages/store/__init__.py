"""Postgres + pgvector access — single entry point for the whole monorepo.

All reads and writes to the vector store go through this package.
Ingestion orchestrates chunking then calls `write_chunks`; the agent
calls `similarity_search`. Nothing else should import `langchain_postgres`
or construct a `PGVector` directly.

The collection name is profile-derived: each model profile gets its own
collection (see `llm.active_collection`). Store functions default to the
active profile's collection when `collection` is not passed.
"""

from llm import active_collection
from store.pgvector import (
    delete_chunks_by_source_paths,
    delete_collection,
    get_vectorstore,
    list_source_paths_under,
    resolve_collection,
    resolve_connection,
    similarity_search,
    write_chunks,
)

__all__ = [
    "active_collection",
    "delete_chunks_by_source_paths",
    "delete_collection",
    "get_vectorstore",
    "list_source_paths_under",
    "resolve_collection",
    "resolve_connection",
    "similarity_search",
    "write_chunks",
]
