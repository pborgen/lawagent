# Data flow

How information moves through lawagent: from the original sources, through
conversion and chunking, into the pgvector store, and out to the agent.

There are **two ingest streams** that converge on the same vector store:

- **Public corpus** — CT statutes, Practice Book, court guides and forms.
  Shareable, not sensitive.
- **Private case file** — the litigant's own documents pulled from CT
  eServices. Sensitive; lives in gitignored `data/case/`.

```
                    ┌─────────────── PUBLIC CORPUS ───────────────┐
                    │                                              │
  jud.ct.gov  ──▶  ingest fetch-public  ──▶  data/raw/public/      │
  (statutes,        (fetch + convert inline)   *.txt  *.md          │
   guides, forms)                              public_sources_      │
                    │                          manifest.json       │
                    └──────────────────────────────┬───────────────┘
                                                    │
                                                    ▼
                                          ingest  (chunk → embed)
                                                    ▲
                    ┌──────────────────────────────┴───────────────┐
                    │                                               │
  CT eServices ──▶  efile pull  ──▶  data/case/efile/<crn>/          │
  (case docket)     (Playwright)       docs/        *.pdf            │
                    │                  pages/case.html  (raw snapshot)│
                    │                  manifest.json                 │
                    │                       │                        │
                    │                       ▼                        │
                    │            pdf2text convert                    │
                    │            (PDF → text, OCR if needed)          │
                    │                       │                        │
                    │                  text/  *.md   (ingestable)    │
                    │                         *.json (per-page        │
                    │                                 provenance)     │
                    │                  pdf2text_manifest.json         │
                    └──────────── PRIVATE CASE FILE ──────────────────┘

                                          │
                              ingest  ──▶ Postgres + pgvector
                                          collection: "ct-divorce"
                                          │
                                          ▼
                              agent  retrieve()  tool
                              (similarity_search via get_vectorstore)
                                          │
                                          ▼
                              cli:  ask / memo / annotate
```

## Stage 1 — Fetch

Raw source material is pulled into `data/` first. Nothing is embedded yet.

### Public corpus → `data/raw/public/`

```
python -m ingest.main fetch-public
```

`apps/ingest` downloads a curated starter set of CT divorce sources. PDF
sources (court forms, law-library guides) are converted to text **inline
during fetch**, so everything lands as `.txt` / `.md` — already ingestable.
A `public_sources_manifest.json` records what was fetched.

### Private case file → `data/case/efile/<crn>/`

```
python -m efile.main pull --crn <crn>
```

`apps/efile` logs into CT eServices with Playwright and walks the case
docket. It writes, under `data/case/efile/<crn>/`:

| Path | Contents |
|------|----------|
| `docs/*.pdf` | every docket-entry document, downloaded as-is |
| `pages/case.html` | raw HTML snapshot of the case page, for later diffing |
| `manifest.json` | docket entries, document URLs, sha256s, download counts |

The scraper **never touches the vector store** — it only downloads. This
keeps fetch / convert / ingest cleanly separable, so a broken scraper can't
corrupt the corpus.

## Stage 2 — Convert (case file only)

The ingest pipeline only consumes `.txt` / `.md`. Public sources already
arrive in that form, but eServices documents are PDFs and must be converted.

```
python -m pdf2text.main convert --crn <crn>
```

`apps/pdf2text` walks `data/case/efile/<crn>/docs/`, converting each PDF
(OCR fallback when a PDF has no text layer) into `data/case/efile/<crn>/text/`:

| Path | Contents |
|------|----------|
| `text/*.md` | RAG-ingestable markdown — the input to Stage 3 |
| `text/*.json` | per-page text + provenance sidecar |
| `pdf2text_manifest.json` | conversion log, keyed by source sha256 (idempotent) |

## Stage 3 — Ingest into the vector store

```
# public corpus
python -m ingest.main data/raw/public

# private case file — point at text/, NOT docs/
python -m ingest.main data/case/efile/<crn>/text
```

`apps/ingest` (logic in `packages/ingestion`) discovers every `.txt` / `.md`
file, chunks it with citation-preserving metadata
(`{source, citation, section, subsection, chunk_index, source_type}`),
embeds the chunks, and writes them to **Postgres + pgvector**.

- Default collection: `ct-divorce`. Pass `--collection` to separate private
  case material from public law (e.g. `--collection ct-divorce-case`).
- `--dry-run` chunks and reports counts without embedding or writing.
- Requires Postgres running (`docker compose up`) and `LAWAGENT_PG_URL` set,
  or an explicit `--connection`.

## Stage 4 — Read: the agent and CLI

Everything downstream reads from pgvector through one function,
`ingestion.get_vectorstore()` — the agent never imports from `apps/ingest`.

- `apps/agent` exposes a `retrieve(query, k, source_type)` LangGraph tool
  (`apps/agent/src/tools.py`) that runs `similarity_search` against the
  store and returns passages with their citations.
- `apps/cli` is the user surface: `lawagent ask` / `memo` / `annotate`.

Answers are grounded **only** in retrieved chunks, and each chunk carries
its citation so claims can be traced back to a real source.

## Where data comes to rest

| Location | Written by | Purpose |
|----------|-----------|---------|
| `data/raw/public/` | `ingest fetch-public` | public source text + manifest |
| `data/case/efile/<crn>/docs/` | `efile pull` | original case PDFs |
| `data/case/efile/<crn>/pages/` | `efile pull` | raw HTML snapshot for diffing |
| `data/case/efile/<crn>/text/` | `pdf2text convert` | converted markdown + sidecars |
| `data/case/efile/<crn>/*.json` | `efile` / `pdf2text` | download + conversion manifests |
| `data/debug/` | `efile capture` | ad-hoc page snapshots for debugging |
| Postgres / pgvector | `ingest` | embeddings + chunk text + metadata |

All of `data/` is gitignored. The private case file under `data/case/`
must never be committed.

## Quick reference — full pipeline for a new case

`apps/pipeline` runs stages 1-3 as one command and does only what's needed —
it skips fetch if the PDFs are already downloaded, and skips ingest if the
converted text hasn't changed since the last run:

```
python -m pipeline.main run --crn <crn>        # stages 1-3, idempotent
python -m pipeline.main run --crn <crn> --refresh   # force every stage
python -m cli.main ask "..."                   # 4. query
```

Or run the stages by hand:

```
python -m efile.main pull --crn <crn>          # 1. fetch PDFs from eServices
python -m pdf2text.main convert --crn <crn>    # 2. PDF → markdown
python -m ingest.main data/case/efile/<crn>/text   # 3. chunk + embed → pgvector
```

The pipeline records its progress in `data/case/efile/<crn>/.pipeline_state.json`
(a fingerprint of the converted text) so a re-run with nothing new is a near no-op.
