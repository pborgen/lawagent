from __future__ import annotations

from typing import Any, Optional

from langchain_core.documents import Document
from langchain_postgres import PGVector
from sqlalchemy import create_engine, text

from corpus import Chunk
from llm import active_collection, get_active_profile, get_embeddings
from settings import get_settings


def resolve_connection(connection: Optional[str] = None) -> str:
    return connection or get_settings().require_pg_url()


def resolve_collection(collection: Optional[str] = None) -> str:
    """A collection name, defaulting to the active profile's collection.

    Each profile's embeddings model writes to its own collection — see
    `llm.active_collection` — so callers normally pass nothing and let
    the active profile decide.
    """
    return collection or active_collection()


def get_vectorstore(
    *,
    collection: Optional[str] = None,
    connection: Optional[str] = None,
) -> PGVector:
    """Return a PGVector handle for the given (or active-profile) collection.

    Assumes the `vector` extension is already enabled on the target database
    (see docker-compose.yml for local dev).

    `collection_metadata` records which embeddings provider+model produced
    the vectors. It is written to `langchain_pg_collection.cmetadata` only
    when the collection is first created — existing collections keep the
    metadata they were tagged with on first ingest.
    """
    embeddings_cfg = get_active_profile().embeddings
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=resolve_collection(collection),
        connection=resolve_connection(connection),
        use_jsonb=True,
        collection_metadata={
            "embeddings_provider": embeddings_cfg.provider,
            "embeddings_model": embeddings_cfg.model,
        },
    )


def write_chunks(
    chunks: list[Chunk],
    *,
    collection: Optional[str] = None,
    connection: Optional[str] = None,
) -> None:
    """Embed chunk texts and upsert them into the vector store."""
    vectorstore = get_vectorstore(collection=collection, connection=connection)
    vectorstore.add_texts(
        texts=[c.text for c in chunks],
        metadatas=[c.to_metadata_dict() for c in chunks],
        ids=[c.id for c in chunks],
    )


def similarity_search(
    query: str,
    *,
    k: int = 6,
    collection: Optional[str] = None,
    connection: Optional[str] = None,
    filter: Optional[dict[str, Any]] = None,
) -> list[Document]:
    """Return the top-k passages most similar to `query`."""
    return get_vectorstore(collection=collection, connection=connection).similarity_search(
        query, k=k, filter=filter
    )


def delete_collection(
    *,
    collection: Optional[str] = None,
    connection: Optional[str] = None,
) -> None:
    """Drop a collection and all of its embeddings."""
    get_vectorstore(collection=collection, connection=connection).delete_collection()


def list_source_paths_under(
    prefix: str,
    *,
    collection: Optional[str] = None,
    connection: Optional[str] = None,
) -> list[str]:
    """Distinct `source_path` values in `collection` that start with `prefix`.

    Used by the prune step to find which on-disk files this collection
    currently has chunks for — the caller then drops any whose file is gone.
    """
    name = resolve_collection(collection)
    sql = text(
        """
        SELECT DISTINCT e.cmetadata->>'source_path' AS source_path
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON e.collection_id = c.uuid
        WHERE c.name = :name
          AND e.cmetadata->>'source_path' LIKE :pat
        """
    )
    engine = create_engine(resolve_connection(connection))
    with engine.connect() as conn:
        rows = conn.execute(sql, {"name": name, "pat": f"{prefix}%"}).all()
    return [r[0] for r in rows if r[0]]


def delete_chunks_by_source_paths(
    paths: list[str],
    *,
    collection: Optional[str] = None,
    connection: Optional[str] = None,
) -> int:
    """Delete chunks in `collection` whose source_path is in `paths`.

    Returns the number of rows removed. No-op (returns 0) when `paths` is empty.
    """
    if not paths:
        return 0
    name = resolve_collection(collection)
    sql = text(
        """
        DELETE FROM langchain_pg_embedding
        WHERE collection_id = (
            SELECT uuid FROM langchain_pg_collection WHERE name = :name
        )
          AND cmetadata->>'source_path' = ANY(CAST(:paths AS TEXT[]))
        """
    )
    engine = create_engine(resolve_connection(connection))
    with engine.begin() as conn:
        result = conn.execute(sql, {"name": name, "paths": paths})
        return result.rowcount or 0
