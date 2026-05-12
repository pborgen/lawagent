# Spike Plan

A small, throwaway-tolerant prototype to validate the core loop:
**curated CT alimony corpus → pgvector (Postgres) → LangGraph + Claude
→ grounded, cited answer about a real alimony question from the
author's case.**

**Time budget:** the author's trial is within 4 weeks of 2026-05-09.
The spike must produce something the author can use to prep for that
trial — not a perfect tool. If it works, harden the parts that matter
for trial; if it doesn't, fall back to manual research with no time
wasted on infra.

## Success criteria for the spike

The spike is a success if, on **5 real alimony questions from the
author's case** (pendente lite vs. final, factors under § 46b-82,
duration, modification, etc.), the agent produces:

1. An answer in the requested mode (memo / short answer / annotated).
2. Citations that resolve to specific CGS sections, Practice Book rules,
   or CT cases — and those citations are correct (not hallucinated, not
   misattributed).
3. Output the author would actually use as a starting point — i.e.
   verifying it takes minutes, not hours.

If 4 of 5 hit, keep going. If 2 of 5 hit, figure out whether the
problem is retrieval, the LLM, the prompt, or the corpus before doing
more.

## Non-goals for the spike

- No web UI. CLI / a Jupyter notebook is fine.
- No multi-user, no auth, no deployment.
- No fancy eval harness — manual scoring on the 5 questions is fine.
- No support for ingesting the author's case documents yet (defer to
  v0.2). The spike runs against the public CT corpus only, with the
  author's facts pasted into the prompt.

## Scope of the spike

### Corpus (alimony-focused, small)
- CGS §§ 46b-82, 46b-83 (alimony, pendente lite alimony).
- CGS §§ 46b-86, 46b-87 (modification, contempt) — adjacent.
- CT Practice Book Ch. 25 sections relevant to alimony motions.
- 10–15 CT appellate alimony cases, hand-picked by the author.

Total target size: small enough that retrieval bugs are visible by
inspection.

### Pipeline
1. Drop raw documents into `data/raw/`.
2. `apps/ingest`: parse, chunk with citation metadata, embed, write to
   the pgvector store on Postgres (local Docker or Aurora/RDS).
3. `apps/agent`: a LangGraph agent with a `retrieve` tool over the
   vector store and an Anthropic Claude LLM.
4. `apps/cli`: `lawagent ask "..."` and `lawagent memo "..."`.

### Eval set
Build 5 real questions from the author's actual case prep, with
hand-noted "correct citations" and "key points" expected in the
answer. Score each spike run against this set.

## Sequence

1. **Pick embedding provider** — Voyage or OpenAI; either is fine.
   Trivial decision now that privacy isn't a constraint.
2. **Scaffold monorepo** — `pyproject.toml`, `apps/{ingest,agent,cli}`,
   `packages/corpus`, gitignored `data/`.
3. **Get a small corpus loading** — even just CGS §§ 46b-40..87 is
   enough to start.
4. **Wire ingest → vector DB** — chunking with citation metadata.
   Inspect chunks manually before going further.
5. **Wire a minimal LangGraph agent** with a single `retrieve` tool +
   Claude. No agent loop tricks yet — one retrieve, one draft.
6. **Run the 5 eval questions, by hand-score.** Iterate.
7. **Add output modes** (memo / short / annotated) only after the
   single mode works.

## What we're explicitly punting until after the spike

- Ingesting the author's private case documents.
- Multi-step agent reasoning (retrieve → reason → retrieve again).
- Citation verification automation (detecting hallucinated cites).
- Any UI beyond the CLI.

## When to abandon the spike

Pull the plug if any of these are true after a real attempt:

- Citations are still hallucinated >20% of the time after prompt-tuning.
  (Probably means we need a stricter retrieval-then-generate pattern,
  or a different model.)
- Retrieval surfaces the wrong sections of CGS for plain-English queries
  even after chunking improvements. (Probably means the chunking /
  metadata model is wrong.)
- The author's verification time is longer than just doing the research
  manually. (The product has no value.)
