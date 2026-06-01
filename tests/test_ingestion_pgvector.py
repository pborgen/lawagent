"""Real integration test for the document → pgvector ingestion step.

This is the part of the app that takes document data and stores it in the
vector DB: `packages/ingestion/pipeline.py`. The flow is

    discover_files()  →  chunk_files()  →  write_chunks()
       find .txt/.md      split into Chunks    embed + INSERT into pgvector

`store.write_chunks()` calls `PGVector.add_texts()`, which does two things
in one step: runs each chunk's text through the embeddings model (Voyage or
OpenAI) and inserts the resulting vector + JSONB metadata into Postgres.

This test exercises that for real — it talks to the Postgres+pgvector
database from docker-compose.yml and calls the configured embeddings
provider. It skips itself automatically when either dependency is missing,
so a plain `pytest` run never fails just because the DB is down.

To run it for real:

    docker compose up -d db          # start Postgres + pgvector
    # make sure VOYAGE_API_KEY (or OPENAI_API_KEY) is set in your .env
    pytest tests/test_ingestion_pgvector.py -v -s

The `-s` flag lets the step-by-step prints through, so you can watch the
pipeline work.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg
import pytest

from ingestion.pipeline import ingest
from store import delete_collection, similarity_search
from llm import get_active_profile
from settings import get_settings


# Maps hosted providers to the env var their SDK reads. Local needs no key.
_PROVIDER_KEY = {"voyage": "VOYAGE_API_KEY", "openai": "OPENAI_API_KEY"}


def _local_embeddings_available() -> bool:
    try:
        import langchain_huggingface  # noqa: F401
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def _pg_reachable(sqlalchemy_url: str) -> bool:
    """True if we can open a TCP connection to the Postgres in pg_url.

    The app stores a SQLAlchemy-style URL (`postgresql+psycopg://...`);
    psycopg.connect() wants a plain DSN, so we drop the `+psycopg` driver tag.
    """
    dsn = sqlalchemy_url.replace("+psycopg", "")
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def pg_url() -> str:
    """A reachable pgvector connection string, or skip the whole module."""
    settings = get_settings()
    url = settings.pg_url
    if not url:
        pytest.skip("LAWAGENT_PG_URL not set — see .env.example")
    if not _pg_reachable(url):
        pytest.skip(f"Postgres not reachable at {url} — run `docker compose up -d db`")

    provider = get_active_profile().embeddings.provider
    if provider == "local":
        if not _local_embeddings_available():
            pytest.skip(
                "local embeddings deps not installed — run `uv sync --group local`"
            )
    else:
        # Hosted providers (voyage/openai) need an API key; keyless providers
        # (ollama, bedrock via the AWS chain) have no env-var gate here.
        key = _PROVIDER_KEY.get(provider)
        if key and not os.environ.get(key):
            pytest.skip(f"{key} not set — needed to embed chunks with the real provider")
    return url


@pytest.fixture
def collection(pg_url: str):
    """A unique throwaway collection name, dropped again after the test.

    Using a random name keeps this test from touching the real
    `ct-divorce` collection your app actually queries.
    """
    name = f"test-ingest-{uuid.uuid4().hex[:8]}"
    yield name
    # Teardown: drop the collection so the DB is left exactly as we found it.
    try:
        delete_collection(collection=name, connection=pg_url)
    except Exception:
        pass


def test_ingest_writes_a_document_into_pgvector(tmp_path: Path, pg_url: str, collection: str) -> None:
    # --- 1. Arrange: a sample statute file on disk, the way `ingest` expects --
    # The `cgs-` prefix tells the chunker this is a Connecticut statute, so it
    # splits by section/subsection and derives a "Conn. Gen. Stat. §" citation.
    doc = tmp_path / "cgs-46b-56.txt"
    doc.write_text(
        "Sec. 46b-56. Orders re custody, care, education, visitation and "
        "support of children.\n\n"
        "(a) In any controversy before the Superior Court as to the custody "
        "of minor children, the court may make any proper order regarding "
        "custody and visitation according to its best judgment upon the "
        "facts of the case.\n",
        encoding="utf-8",
    )

    # --- 2. Act: run the real pipeline (discover → chunk → embed → write) ----
    files, chunks = ingest(doc, collection=collection, connection=pg_url)
    print(f"\n[ingest] discovered {len(files)} file(s), produced {len(chunks)} chunk(s)")

    # --- 3. Assert: the pipeline reported what it did ------------------------
    assert files == [doc]
    assert len(chunks) == 1, "the single (a) subsection should yield one chunk"
    chunk = chunks[0]
    print(f"[chunk]  id={chunk.id}  citation={chunk.metadata.citation!r}")
    assert chunk.metadata.section == "46b-56"
    assert chunk.metadata.subsection == "(a)"
    assert chunk.metadata.citation == "Conn. Gen. Stat. § 46b-56(a)"

    # --- 4. Assert: the row is really in pgvector and semantically findable --
    # This is the payoff — we query with words that do NOT appear verbatim in
    # the text, so a hit proves the embedding + vector search round-tripped.
    hits = similarity_search(
        "who decides where a child lives?",
        k=1,
        collection=collection,
        connection=pg_url,
    )
    print(f"[search] {len(hits)} hit(s) for the semantic query")

    assert hits, "expected the ingested chunk to come back from a vector search"
    top = hits[0]
    assert "custody" in top.page_content.lower()
    # Metadata round-tripped through the Postgres JSONB column.
    assert top.metadata["section"] == "46b-56"
    assert top.metadata["citation"].startswith("Conn. Gen. Stat.")
