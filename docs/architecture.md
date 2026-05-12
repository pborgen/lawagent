# Architecture (proposed)

This is a sketch, not a commitment. The spike will pressure-test it.

## Stack direction

- **Language:** Python (matches `socialmedia` repo conventions; LangChain
  is most mature in Python).
- **Agent framework:** LangChain (and likely LangGraph for the agent loop).
- **LLM:** Anthropic Claude via the Anthropic SDK (default). Chosen for
  long context (good for legal docs) and citation-friendly outputs.
- **Embeddings:** hosted — `voyage-3` (default) or OpenAI
  `text-embedding-3-small`. Both wired through `llm.get_embeddings()`.
- **Vector DB:** **pgvector** on Postgres — local Docker for dev,
  Aurora PostgreSQL or RDS PostgreSQL on AWS. Same `langchain-postgres`
  interface in both environments. Chosen for hybrid SQL+vector queries,
  managed-backups story, and resume-legible AWS surface area.
- **Repo:** Monorepo. Mirrors `socialmedia/`: root `pyproject.toml`,
  `apps/<name>/{main.py,src/}` per app, shared code in `packages/`.

## Monorepo layout

```
lawagent/
├── pyproject.toml             # deps + setuptools find over apps/ + packages/
├── README.md
├── docs/                      # requirements (this folder)
├── apps/
│   ├── ingest/                # CLI: `python -m ingest.main data/raw/`
│   ├── agent/                 # LangGraph trial-prep agent
│   ├── cli/                   # `lawagent` entrypoint
│   └── efile/                 # CT eServices scraper (Playwright)
├── packages/
│   ├── corpus/                # shared schemas (Chunk, DocumentMetadata, Citation)
│   ├── ingestion/             # chunking + ingest pipeline (separate from agent)
│   └── llm/                   # ⭐ chat model + embeddings — single source of truth
├── data/
│   ├── raw/                   # source documents (gitignored)
│   └── case/                  # the author's private case docs (gitignored)
├── docker-compose.yml         # local Postgres + pgvector for dev
```

### Why ingestion is its own package

`packages/ingestion/` exists so the agent never imports anything from
`apps/ingest/`. The agent reads from the pgvector store via
`ingestion.get_vectorstore()`; ingestion writes through the same
function. Everything else stays decoupled.

### Why `apps/efile/` is a separate process

The scraper is a single-purpose tool: log in to CT eServices, pull
case data + documents into `data/case/efile/<crn>/`, write a
manifest. It does not touch the vector store directly. After it runs,
you (or a cron) can ingest the new docs with the normal ingest CLI.
This keeps three concerns cleanly split — fetch, ingest, query —
and means a broken scraper can't corrupt the corpus.

The scraper uses Playwright (real Chromium) for ASP.NET / ViewState
robustness, and adds randomized polite waits between every navigation
and download to avoid getting timed out by the portal.

### Why `packages/llm/` is the single source of truth

Every chat-model and embedding-model construction goes through
`llm.get_chat_model()` / `llm.get_embeddings()`. Provider, model,
temperature, and max-tokens are all driven by env vars
(`LAWAGENT_LLM_PROVIDER`, `LAWAGENT_LLM_MODEL`, etc.), so swapping
between Claude and GPT — or trying a cheaper model in dev — is a
.env change, not a code change.

`data/` is gitignored. The author's own case documents live there and
must never be committed.

## Core data flow

1. **Ingest** (`apps/ingest`):
   - Pull / load raw CT statutes (Title 46b), Practice Book chapters,
     curated case PDFs.
   - Parse → normalize → chunk with citation-preserving metadata
     (`{source, citation, section, subsection, chunk_index}`).
   - Embed and write to the vector store.

2. **Query / agent loop** (`apps/agent`):
   - User submits a task (question / statute / fact pattern + question).
   - Agent (LangGraph) plans, calls a `retrieve(query, filters)` tool
     against the vector DB, possibly iterates, then drafts.
   - Output is rendered in the requested mode (memo / short answer /
     annotated). Every claim is anchored to a retrieved chunk so cites
     can be checked deterministically.

3. **CLI / surface** (`apps/cli`):
   - `lawagent ask "..."` → short answer
   - `lawagent memo "..."` → memo
   - `lawagent annotate <statute>` → annotated view

## Citation discipline

This is the architectural keystone. The agent must:

- Only state legal claims that trace back to a retrieved chunk.
- Render citations in standard CT form (`Conn. Gen. Stat. § 46b-82(a)`,
  `Conn. Practice Book § 25-26`, `Smith v. Smith, 333 Conn. 1 (2019)`).
- Preserve a chunk-id → claim-id map so we can later auto-verify that
  every claim has a real source. Hallucinated cites are the failure
  mode that kills the product; we instrument against it from day one.

## Privacy posture

Out of scope as a design constraint. Hosted embeddings, hosted LLM
(Anthropic), and a local vector store are all fine. Case documents
still live in gitignored `data/case/` to avoid accidentally committing
them, but no special handling beyond that.
