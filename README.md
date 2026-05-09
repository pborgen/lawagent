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
│   ├── ingestion/   # ingestion pipeline (chunking + write to Chroma)
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
uv sync                      # or: pip install -e .
playwright install chromium  # only needed if you'll use apps/efile

# 2. Configure
cp .env.example .env
# fill in ANTHROPIC_API_KEY and one of VOYAGE_API_KEY / OPENAI_API_KEY
# (and EFILE_USERNAME / EFILE_PASSWORD if you'll scrape eServices)

# 3. Drop CT statute/case text files into data/raw/

# 4. Ingest the public corpus
python -m ingest.main data/raw/

# 5. (Optional) Pull your case from CT eServices
python -m efile.main pull            # downloads to data/case/efile/<crn>/

# 6. Ask
python -m cli.main ask "What factors does CGS 46b-82 require the court to consider?"
```

## Stack

Python 3.11+, LangChain + LangGraph, Chroma (local), Anthropic Claude,
Voyage or OpenAI embeddings.
