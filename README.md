# lawagent

A trial-prep assistant for a pro se litigant in a Connecticut divorce.
**Initial focus: alimony** (CGS §§ 46b-82, 46b-83).

> ⚠️ Not legal advice. This tool helps the author research and think
> about CT divorce law, grounded in the statutes and cases it has been
> given. It does not replace a lawyer.

## Status

Scaffolding stage. See [docs/](docs/) for vision, MVP scope, and the
spike plan.

## Layout

```
lawagent/
├── apps/
│   ├── ingest/      # CLI: `python -m ingest.main data/raw/`
│   ├── agent/       # LangGraph agent: retrieve → reason → cite
│   ├── cli/         # `lawagent ask|memo|annotate "..."` entrypoint
│   ├── api/         # FastAPI: HTTP /chat wrapper around the agent
│   ├── web/         # Next.js frontend — landing page + /chat chatbot
│   └── efile/       # CT eServices scraper (Playwright); pulls case docs
├── packages/
│   ├── corpus/      # shared schemas (chunks, citations, source types)
│   ├── store/       # Postgres + pgvector reads/writes (single DB boundary)
│   ├── ingestion/   # chunking + ingest orchestration (calls store)
│   └── llm/         # ⭐ single source of truth for chat model + embeddings
├── config/          # model profiles (profiles.yaml)
├── data/            # gitignored: raw docs, vector store, case files
└── docs/            # requirements
```

To swap models, change `LAWAGENT_PROFILE` in your `.env` — each profile
bundles a chat model with its matching embeddings (and its own pgvector
collection). Profiles are defined in `config/profiles.yaml`; add one to
support a new model. Code only ever touches `from llm import
get_chat_model` / `get_embeddings` — nothing in `apps/` constructs
models or picks providers directly.

## Setup

```bash
# 1. Install (uv recommended; pip works too)
uv sync --group local        # default embeddings are local (CPU, no API key)
# or: pip install -e ".[local]"
playwright install chromium  # only needed if you'll use apps/efile

# 2. Configure
cp .env.example .env
# The default profile (LAWAGENT_PROFILE=local) needs no API key.
# To use a hosted model, set LAWAGENT_PROFILE=anthropic|openai and the
# matching API keys. Profiles are defined in config/profiles.yaml.
# (set EFILE_USERNAME / EFILE_PASSWORD too if you'll scrape eServices)

# 3. Start Postgres + pgvector (local dev)
docker compose up -d db
# LAWAGENT_PG_URL in .env points at this by default. For AWS, point it
# at Aurora PostgreSQL or RDS PostgreSQL with the `vector` extension
# enabled.

# 4. Fetch a starter set of official CT divorce sources
python -m ingest.main fetch-public
#
#    Or drop your own CT statutes, Practice Book, court guides/forms, and case
#    text files into data/raw/. See docs/corpus-format.md for filename/frontmatter
#    conventions.

# 5. Ingest the public corpus
python -m ingest.main data/raw/public --dry-run
python -m ingest.main data/raw/public

# 6. (Optional) Pull your case from CT eServices
python -m efile.main pull            # downloads to data/case/efile/<crn>/

# 7. Ask (CLI)
python -m cli.main ask "What factors does CGS 46b-82 require the court to consider?"
```

## Chatbot (web frontend)

The same agent is exposed as a chatbot. It runs as two processes: the
Python agent API and the Next.js frontend.

```bash
# Terminal 1 — agent API (FastAPI on http://127.0.0.1:8000)
lawagent-api
# or: uvicorn api.main:app --reload --port 8000

# Terminal 2 — web frontend (Next.js on http://localhost:3000)
cd apps/web
npm install        # first run only
npm run dev
```

Open <http://localhost:3000/chat>. The browser POSTs to the Next.js
route `/api/chat`, which proxies to the FastAPI `/chat` endpoint — so
the agent URL stays server-side. To point the frontend at a non-local
agent, set `AGENT_API_URL` in `apps/web/.env.local` (defaults to
`http://127.0.0.1:8000`).

## Stack

Python 3.11+, LangChain + LangGraph, **pgvector on Postgres** (local
Docker or Aurora/RDS on AWS). Models are chosen by *profile*
(`config/profiles.yaml`, selected with `LAWAGENT_PROFILE`). The default
`local` profile runs both **chat model and embeddings locally** with no
API key — HuggingFace transformers (`Qwen/Qwen2.5-3B-Instruct`) and
sentence-transformers. The `anthropic` and `openai` profiles swap in
hosted Claude / GPT models and their embeddings.
