from __future__ import annotations

from typing import Any, Optional

from langchain_core.documents import Document
from langchain_postgres import PGVector

from corpus import Chunk
from llm import get_embeddings
from settings import get_settings


DEFAULT_COLLECTION = "ct-divorce"


def resolve_connection(connection: Optional[str] = None) -> str:
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
        connection=resolve_connection(connection),
        use_jsonb=True,
    )


def write_chunks(
    chunks: list[Chunk],
    *,
    collection: str = DEFAULT_COLLECTION,
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
    collection: str = DEFAULT_COLLECTION,
    connection: Optional[str] = None,
    filter: Optional[dict[str, Any]] = None,
) -> list[Document]:
    """Return the top-k passages most similar to `query`."""
    return get_vectorstore(collection=collection, connection=connection).similarity_search(
        query, k=k, filter=filter
    )


def delete_collection(
    *,
    collection: str,
    connection: Optional[str] = None,
) -> None:
    """Drop a collection and all of its embeddings."""
    get_vectorstore(collection=collection, connection=connection).delete_collection()
