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
│   └── efile/       # CT eServices scraper (Playwright); pulls case docs
├── packages/
│   ├── corpus/      # shared schemas (chunks, citations, source types)
│   ├── ingestion/   # ingestion pipeline (chunking + write to pgvector)
│   └── llm/         # ⭐ single source of truth for chat model + embeddings
├── data/            # gitignored: raw docs, vector store, case files
└── docs/            # requirements
```

To swap the LLM, change `LAWAGENT_LLM_PROVIDER` / `LAWAGENT_LLM_MODEL`
in your `.env`. Code only ever touches `from llm import get_chat_model` —
nothing in `apps/` constructs models directly.

## Setup

```bash
# 1. Install (uv recommended; pip works too)
uv sync --group local        # default embeddings are local (CPU, no API key)
# or: pip install -e ".[local]"
playwright install chromium  # only needed if you'll use apps/efile

# 2. Configure
cp .env.example .env
# fill in ANTHROPIC_API_KEY
# for hosted embeddings instead of local: set LAWAGENT_EMBEDDINGS=voyage|openai
# and the matching VOYAGE_API_KEY or OPENAI_API_KEY
# (and EFILE_USERNAME / EFILE_PASSWORD if you'll scrape eServices)

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

# 7. Ask
python -m cli.main ask "What factors does CGS 46b-82 require the court to consider?"
```

## Stack

Python 3.11+, LangChain + LangGraph, **pgvector on Postgres** (local
Docker or Aurora/RDS on AWS), Anthropic Claude, and embeddings via
local sentence-transformers by default (or Voyage / OpenAI via
`LAWAGENT_EMBEDDINGS`).
