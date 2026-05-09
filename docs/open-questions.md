# Open Questions

Decisions still pending. Each is a real fork in the road; revisit before
or during the spike.

## Privacy / data handling — RESOLVED (out of scope)

Decided not to treat case-data privacy as a design constraint. Hosted
embeddings, hosted LLM, and a local vector store are all fine. Case
documents stay in gitignored `data/case/` to avoid accidental commits,
but otherwise no special handling. Revisit only if v2 (other users)
forces it.

## Embedding model — pick one before the spike

Two reasonable defaults:

- **Voyage `voyage-3`** — strong on retrieval, popular in the
  Anthropic/LangChain ecosystem, separate API key.
- **OpenAI `text-embedding-3-small`** — solid, cheap, easy if there's
  already an OpenAI key around.

Either is fine; pick on convenience. Switching later is a re-embed of
the corpus, not a rewrite.

## What "the corpus" actually contains in v0

To start the spike we need a concrete, small corpus. Candidates:

- CGS Title 46b — full text. Public, available from the CT General
  Assembly website (free).
- CT Practice Book Chs. 25 / 25a — public, available from the CT
  Judicial Branch website.
- A handful (10–25) of CT appellate decisions on the issues your case
  actually turns on. **You'll need to identify these.** Without this
  pick, the agent will be unevenly grounded.

## Input format(s) the agent should accept

Earlier you flagged "not sure" on the input shape. Reasonable starting
set:

- A bare research question.
- A statute reference + a question about it in your context.
- A fact pattern + a question grounded in those facts.

The spike can support all three; they share retrieval plumbing.

## What signals "good enough" during the spike

We need a small evaluation set: 10–20 questions with hand-curated
"correct" answers (citations + key points). Without this we can't tell
if the agent is improving or regressing. **Action: build this list
before or during the spike, drawing from real questions in your case.**

## License / sharing posture

If this eventually helps other CT pro se litigants:

- Does the codebase get open-sourced?
- Does the corpus get redistributed (statutes are public; some case
  publishers have terms)?
- Do users supply their own case documents on their own machine, or
  does the project ever host their data?

Not urgent for the spike, but worth a position before the v2 audience
starts mattering.

## Disclaimers and "not legal advice"

Even for personal use, output should carry a clear "not legal advice"
header. For other users this becomes a much bigger surface (UPL —
unauthorized practice of law — concerns). Worth a separate decision
before any v2 work.
