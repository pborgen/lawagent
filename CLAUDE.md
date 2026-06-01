# CLAUDE.md

Onboarding for anyone (human or agent) touching this repo. Read it once;
it encodes the conventions, boundaries, and gotchas that aren't obvious
from the file tree. For the *why* behind the design, see [docs/](docs/)
([architecture](docs/architecture.md), [data-flow](docs/data-flow.md)).

## What this is

A trial-prep assistant for a **pro se litigant in a Connecticut divorce**
(initial focus: alimony, CGS §§ 46b-82 / 46b-83). It ingests CT statutes,
the Practice Book, court forms, and the litigant's own case file, then
answers questions with **citations that trace back to retrieved text**.

> Not legal advice. The product's whole value is grounded, checkable
> citations — hallucinated cites are the failure mode that kills it.

## Always run `make check` before you push

```bash
make check     # ruff lint + pytest + web typecheck — ~2s, offline
```

This is the feedback loop: ruff lint + pytest + ESLint + web typecheck. It
mirrors CI and needs no database or API keys. Keep it green. `make help`
lists every target.

- `make py-test` — pytest only. The pgvector/embedding tests **self-skip**
  when there's no reachable DB or no embedding key, so a bare run is safe
  and fast. To actually exercise them: `make db-up`, set `LAWAGENT_PG_URL`
  + the active profile's embedding key, then `make py-test`.
- `make fmt` — ruff formatter. **Opt-in, large diff**: the tree predates
  `ruff format`, so we lint (`ruff check`) but don't enforce formatting.
  Don't run a repo-wide `make fmt` as a drive-by; it buries real changes.

## Golden rules (the boundaries that keep this decoupled)

1. **Models go through `packages/llm/` — nothing else constructs them.**
   Always `from llm import get_chat_model, get_embeddings`. Never
   instantiate a `ChatAnthropic` / `OpenAIEmbeddings` / HF pipeline in
   `apps/`. Which models you get is set by the active **profile**
   (`LAWAGENT_PROFILE`, default `local`), defined in
   [config/profiles.yaml](config/profiles.yaml). Add a model = add a YAML
   entry, not a code change.
   - A profile **bundles chat + embeddings on purpose**: each gets its own
     pgvector collection (`llm.active_collection()`) so you never query
     vectors of the wrong dimension. Switching profiles ⇒ **re-ingest**.
   - **Per state**: `llm.collection_for(slug)` returns `<slug>-law__<model>`
     (e.g. `ny-law__…`). Connecticut keeps the legacy `ct-divorce__<model>`
     base for backward-compat — don't "normalize" it to `ct-law` (that would
     orphan the existing CT vectors). The agent's collection is chosen by the
     caller (`ask(..., state=…)` / `RETRIEVAL_STATE`), never by the LLM.

2. **All vector / DB access goes through a package, never raw in `apps/`.**
   - `packages/store/` — pgvector reads/writes (`write_chunks`,
     `similarity_search`). The agent retrieves *only* through here.
   - `packages/db/` — app data (users, projects) via SQLAlchemy ORM.
   - `packages/ingestion/` — chunking + ingest orchestration; calls
     `store`. It exists so **the agent never imports `apps/ingest/`**.

3. **`apps/` never imports from another `apps/`.** Cross-app needs live in
   `packages/`. Each app is independently runnable; shared logic is shared
   code, not a sibling import. (The CLI and API both call
   `agent.src.graph.ask()` — that's the one agent, reused, not duplicated.)

4. **Config is read through `packages/settings/`**, sourced from `.env`
   (see [.env.example](.env.example)). Don't sprinkle `os.environ` reads.

5. **`data/` is gitignored and stays that way.** The litigant's case
   documents live in `data/case/`. Never commit anything under `data/`.

## Repo map

```
apps/
  cli/        `python -m cli.main ask|memo|annotate "..."`  (typer)
  api/        FastAPI — thin /chat wrapper around the agent; auth, files, projects
  agent/      LangGraph agent: retrieve → reason → cite  (code in agent/src/)
  web/        Next.js 16 frontend (landing + /chat). SEPARATE npm project — see below
  ingest/     `python -m ingest.main ...`  (fetch-public/fetch-state → chunk → embed)
  efile/      CT eServices scraper (Playwright) → data/case/efile/<crn>/
  s3fetch/    mirror an S3 prefix → data/case/s3/<id>/
  pdf2text/   PDF → text (+OCR) → data/case/.../text/
  pipeline/   orchestrates fetch → convert → ingest as subprocesses (idempotent)
  syncd/      apscheduler daemon hosting recurring jobs (jobs/ auto-discovered)
  ccsg1/      one-off: fill the CT CCSG-1 child-support worksheet PDF
packages/
  llm/        ⭐ single source of truth for chat model + embeddings
  store/      Postgres + pgvector boundary (the only vector I/O)
  db/         SQLAlchemy ORM for app data (users, projects)
  ingestion/  chunking + ingest pipeline (calls store)
  corpus/     shared schemas (Chunk, DocumentMetadata, Citation) + state registry
  settings/   env-driven config loader
config/profiles.yaml   model profiles (chat + embeddings bundles)
config/states.yaml     per-state source registry (multi-state, non-CT)
docs/                  vision, architecture, data-flow, mvp-scope, open-questions
```

The data path: **fetch** (efile/s3fetch/ingest fetch-public) → **convert**
(pdf2text) → **ingest** (chunk→embed→pgvector) → **agent** retrieves →
**CLI / web** surface it. There are two ingest streams (public corpus and
private case file) converging on one collection — see
[docs/data-flow.md](docs/data-flow.md).

## Python conventions

- **Drive everything through `uv`**: `uv run pytest`, `uv run python -m ...`,
  `uv sync`. Not bare `python`/`pip`. CI uses `uv sync --frozen`.
- `apps/` and `packages/` are on the path (setuptools find + pytest
  `pythonpath`), so imports are flat: `from llm import ...`,
  `from agent.src.graph import ask`. There's no `src.` top-level prefix
  except inside an app's own `src/` (e.g. `agent.src.graph`).
- Apps are **typer** CLIs exposing `app` / `main`; entrypoints are wired in
  `pyproject.toml [project.scripts]` (`lawagent`, `lawagent-api`).
- New tables use the **`lawagent_*` prefix** so they can't collide with the
  `langchain_pg_*` tables pgvector creates in the same database. Key users
  on `cognito_sub` (stable), never email.

## Web (apps/web) — read this before writing any Next code

- It's a **separate npm project** with its own deps. Use `make install`
  (runs `npm ci`) or `cd apps/web && npm ci`. Types: `make web-types`.
- **This is Next.js 16 + React 19 — not the Next you remember.**
  [apps/web/AGENTS.md](apps/web/AGENTS.md): read the relevant guide under
  `node_modules/next/dist/docs/` before writing code, and heed deprecations.
- The browser never talks to the agent directly: it POSTs to a Next route
  (`/api/chat`, `/api/files/*`, `/api/projects/*`) which proxies to FastAPI,
  keeping `AGENT_API_URL` server-side.

## Auth & security gotchas

- The API verifies every request's bearer token against the Cognito user
  pool's JWKS and enforces an **email allowlist** (`COGNITO_ALLOWED_EMAILS`,
  empty = nobody).
- `LAWAGENT_AUTH_DISABLED=true` is a **dev-only** escape hatch (treats all
  requests as a synthetic user). Never set it in production; App Runner
  leaves it unset. CI's web build uses `AUTH_DISABLED=true` only so
  `next build` doesn't need real credentials.
- This is **multi-tenant** now: files and projects are scoped per user.
  Anything reading/writing user data must scope by the authenticated
  `cognito_sub` — don't widen a query to all rows. (Vector retrieval is
  not yet user-scoped — a known follow-up, not a green light to leak.)

## Case-data discipline

- Case-specific documents come **only** from authenticated eServices
  (`efile`), never from public `civilinquiry`. Public scraping is for the
  shareable corpus (statutes, Practice Book, forms) only.
- The agent must state legal claims **only** when they trace to a retrieved
  chunk, and render cites in standard CT form
  (`Conn. Gen. Stat. § 46b-82(a)`, `Smith v. Smith, 333 Conn. 1 (2019)`).

## Local infra

```bash
make db-up                       # Postgres 16 + pgvector on :5432
docker compose up -d db          # (same thing)
docker compose up api            # build+run the deploy image locally (pre-flight)
```

Deploy target is AWS App Runner (image in ECR, OIDC, no static keys);
`deploy.yml` is **manual-only** (`workflow_dispatch`) until infra is
provisioned. `ci.yml` runs on every push/PR to `main`.
