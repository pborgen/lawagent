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
                              (store.similarity_search)
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

- Default collection: `ct-divorce` (Connecticut). Pass `--state <slug>` to
  target another state's collection (`<slug>-law`), or `--collection` to set
  a name explicitly (e.g. separate private case material from public law).
- `--dry-run` chunks and reports counts without embedding or writing.
- Requires Postgres running (`docker compose up`) and `LAWAGENT_PG_URL` set,
  or an explicit `--connection`.

## Other states — `fetch-state`

CT's public corpus is hand-curated (`fetch-public`, official `jud.ct.gov` /
`cga.ct.gov` URLs). Every other state is **data-driven** from
[config/states.yaml](../config/states.yaml):

```bash
# statutes (public.law) + forms/practice-rules (registry) + optional case law
python -m ingest.main fetch-state --state ny            # --max-sections N to smoke-test
python -m ingest.main data/raw/public/ny --state ny     # ingest into the ny-law collection
python -m ingest.main fetch-state --state tx            # Texas Family Code (deeper layout)
python -m ingest.main data/raw/public/tx --state tx
```

- **Statutes** are crawled from `<state>.public.law`, one frontmatter file
  per section with a jurisdiction-correct citation (`N.Y. Dom. Rel. Law §
  236`, `Tex. Fam. Code § 9.001`). The crawl is polite (`--delay`),
  resumable (skips existing files), and robots-checked.
  - The **section page** (statute text in `<section>` tags, name in
    `<title>`) is identical across states — those parsers and the
    fetch/write loop live in `apps/ingest/src/public_law.py` and are shared.
  - **Navigation differs per state**, so each *shape* has its own discovery
    crawler, selected by the registry's `layout` field (URL scheme is the
    separate `base_path` field — `/laws/`, `/statutes/`, or `/codes/`):
    - `ny_article` — code → `_article_` → `_section_` (NY).
      `apps/ingest/src/public_law.py`.
    - `tx_hierarchical` — deep cumulative `_title_/_subtitle_/_chapter_` tree;
      leaf slugs carry a `_section_` token (TX, CA).
      `apps/ingest/src/public_law_tx.py`.
    - `flat_section` — containers nest, but leaf sections are flat
      `<section_prefix>_<number>` slugs with no `_section_` token (FL, OR, CO,
      NV). `apps/ingest/src/public_law_flat.py`.
    A new shape = a new discovery fn (its own file) + a `layout` entry;
    everything below navigation (robots, section-page parsing, fetch/write) is
    reused. States sharing a shape share a crawler — adding such a state is
    config-only.
- **States not on public.law use bespoke official-site crawlers**
  (`fetcher: official` + an `official_handler` → `apps/ingest/src/official_<slug>.py`,
  dispatched by `_OFFICIAL_CRAWLERS` in `apps/ingest/main.py`). Each official
  legislature site is unique, so each is its own module — but they all reuse
  `public_law.write_statute_section` (the single frontmatter sink) and
  `fetch_html`, so only the navigation/extraction differs. Current official
  states: IL (`ilga.gov`, 750 ILCS 5), OH (`codes.ohio.gov`, R.C. 3105), PA
  (`legis.state.pa.us`, 23 Pa.C.S.), NC (`ncleg.gov`, G.S. Ch. 50), MI
  (`legislature.mi.gov`, MCL 552), VA (`law.lis.virginia.gov`, Title 20 Ch. 6),
  WA (`app.leg.wa.gov`, RCW 26.09), AZ (`azleg.gov`, A.R.S. Title 25 Ch. 3),
  MA (`malegislature.gov`, M.G.L. ch. 208), IN (`iga.in.gov`, IC Title 31
  Art. 15), MO (`revisor.mo.gov`, RSMo ch. 452), MD (`mgaleg.maryland.gov`,
  Fam. Law Titles 7 & 11). Some need quirks — e.g. IN gates its static files
  on a browser User-Agent (`fetch_html_browser`); MD enumerates via a
  `GetNext` JSON walk rather than a TOC.
- **Connecticut** is the special official case: `official_handler: ct_bespoke`
  delegates to `fetch-public` (official `cga.ct.gov` / `jud.ct.gov`) and keeps
  the legacy `ct-divorce` collection (every other state is `<slug>-law`).
- **Covered states** (20): CT, NY, TX, CA, FL, OR, CO, NV (uniform sources) +
  IL, OH, PA, NC, MI, VA, WA, AZ, MA, IN, MO, MD (official sites). public.law
  covers only 7 states; the rest need per-state official crawlers, vetted
  individually. When a source fails the checks the state is skipped rather
  than ingested with bad data:
  - **Skipped — stale:** GA (only free source `ga.elaws.us` is a 2013 snapshot).
  - **Deferred — JS-locked (need Playwright/licensed feed):** NJ (njleg LIS
    Folio-NXT app), TN (T.C.A. is LexisNexis-only).
  - Aggregators (Justia/FindLaw) bot-block (403) across the board.
- **Forms / practice rules** are explicit per-state URL specs in the
  registry, fetched through the same `_fetch_one` path as CT. Many official
  court sites block bots (NY's `nycourts.gov` returns 403) — leave those
  lists empty when unreachable; statutes are the reliable backbone.
- **Case law** (optional, `--cases`) is a bounded seed from CourtListener
  (`apps/ingest/src/courtlistener.py`); needs `COURTLISTENER_API_TOKEN` and
  skips cleanly without it.
- **Per-state collections:** each state writes to `<slug>-law__<model>`
  (e.g. `ny-law__nomic-embed-text`) via `llm.collection_for(slug)`.
  Connecticut keeps the legacy `ct-divorce__<model>` base for backward-compat
  (no re-ingest). The agent's collection is set per request (see Stage 4),
  never by the LLM.

Add a state = add a block to `config/states.yaml`, not code.

## Stage 4 — Read: the agent and CLI

Everything downstream reads from pgvector through one function,
`store.similarity_search()` — the agent never imports from `apps/ingest`.

- `apps/agent` exposes a `retrieve(query, k, source_type)` LangGraph tool
  (`apps/agent/src/tools.py`) that runs `similarity_search` against the
  store and returns passages with their citations. Which state's collection
  it reads is set by the caller via the `RETRIEVAL_STATE` ContextVar
  (`ask(..., state="ny")`), not chosen by the LLM; `None` → Connecticut.
- `apps/cli` is the user surface: `lawagent ask` / `memo` / `annotate`.

Answers are grounded **only** in retrieved chunks, and each chunk carries
its citation so claims can be traced back to a real source.

## Where data comes to rest

| Location | Written by | Purpose |
|----------|-----------|---------|
| `data/raw/public/` | `ingest fetch-public` | CT public source text + manifest |
| `data/raw/public/<state>/` | `ingest fetch-state` | other states' public source text + manifest |
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
