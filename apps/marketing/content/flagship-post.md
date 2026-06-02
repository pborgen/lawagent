# How I built a legal assistant that can't fake a citation

> Flagship technical post (idea #14). The linchpin asset — Show HN (#10),
> LawSites pitch (#6), LinkedIn (#18), and the *Mata* post (#16) all link here.
> Status: **DRAFT — grounded in the real code** (`apps/agent/src/`,
> `packages/store/`, `packages/llm/`, `config/profiles.yaml`). Verify file/
> function names at publish time and add the demo GIF. No case PII in any
> screenshot.

## Working titles (pick one)
- *How I built a legal assistant that can't fake a citation*
- *The fix for AI legal hallucinations isn't a better model — it's architecture*
- *Grounded citations or nothing: building legal RAG you can actually check*

## Audience
Legaltech builders, A2J technologists, engineers evaluating RAG. They know
LLMs hallucinate; they don't know *this* architecture.

---

## The opening

In 2023, two lawyers were sanctioned in *Mata v. Avianca* for filing a brief
full of cases that didn't exist. ChatGPT had invented them — fake names, fake
quotes, fake docket numbers — and the lawyers filed them without checking. The
takeaway most people drew was "AI isn't ready for law."

I think that's the wrong lesson. **A hallucinated citation isn't a model
problem you tune away — it's an architecture problem you design away.** I built
lawagent, a research assistant for people representing themselves in
Connecticut divorce cases, around one rule: the user can click any citation and
see the exact source text it came from. If there's no retrieved source, there's
no citation to click. Here's how that's enforced in code, not in hope.

## Why "just use a better model" doesn't cut it

A more capable model hallucinates *less*, not *never*. For a court filing,
"less" is still sanctionable. And the failure is specific and detectable: the
model emits a citation it cannot point to a source for. So instead of trying to
make that *rare*, I made the citations the user actually relies on come from
somewhere other than the model's free text.

## The shape: retrieve → reason → cite

The agent is a small LangGraph ReAct agent (`create_agent` in
[apps/agent/src/graph.py](../../../apps/agent/src/graph.py)) with exactly one
tool: `retrieve`. The model can't answer from parametric memory and call it a
day — to say anything about the law it has to call `retrieve`, which does a
vector similarity search over the ingested corpus (CT statutes, the Practice
Book, court forms, the user's own case file).

The system prompt's first hard rule
([apps/agent/src/prompts.py](../../../apps/agent/src/prompts.py)) is blunt:

> *Every legal proposition you state MUST be grounded in a passage you
> retrieved with the `retrieve` tool. If you do not have a retrieved passage
> that supports a claim, do not make the claim — say "the corpus doesn't cover
> this" instead.*

That's necessary but not sufficient — a prompt rule is a request, not a
guarantee. The guarantee lives one level down.

## The part that's structural, not aspirational

The citations the UI renders as **clickable sources don't come from the model's
text at all.** Inside the `retrieve` tool
([apps/agent/src/tools.py](../../../apps/agent/src/tools.py)), every chunk that
comes back is recorded — citation, `source_url`, source type — straight from
the chunk's own metadata into a `ContextVar` (`RETRIEVAL_RECORDER`). After the
run, `ask_with_sources()` reads that recorder, not the answer string, to build
the sources panel. As the code comment puts it, these "reflect what the agent
actually pulled — not whatever URLs the LLM remembered or invented."

So the URL behind a citation is a property of a document that was actually
retrieved. The model is explicitly told (rule 2): render a citation as a
markdown link **only** when the retrieve tool showed a `URL:` line, and *never
invent a URL*. A fabricated case can't acquire a working, traceable link,
because links are minted from retrieved metadata, not generated as tokens.

Two more things the *caller* controls, never the model:
- **Jurisdiction.** Which collection gets searched is a second `ContextVar`
  (`RETRIEVAL_STATE`), set by the request, not a tool argument — so the LLM
  can't wander into the wrong state's law, and concurrent requests don't cross
  collections.
- **The retrieval boundary.** All vector I/O goes through `packages/store/`
  (`similarity_search`); the agent never touches Postgres directly. One choke
  point is what makes "only answer from retrieved text" auditable instead of a
  vibe.

## Keeping the vectors themselves trustworthy

Grounding is worthless if you silently retrieve garbage. The subtle failure in
multi-model RAG is querying a collection with embeddings of the wrong
dimension or model. lawagent forecloses it with **profiles**
([config/profiles.yaml](../../../config/profiles.yaml)): a profile *bundles* a
chat model with the embeddings model it must be paired with, and each profile's
embeddings model gets its **own pgvector collection** —
`<collection_base>__<embeddings-model-slug>`, resolved by
`llm.active_collection()`. Switch profiles (say, local HuggingFace → Anthropic
Claude + Voyage → Bedrock Titan) and you query a different collection; you can't
accidentally compare voyage-3 vectors against bge-small vectors. The cost is
honest and stated up front: **switching profiles means re-ingesting.**

This also means the architecture is provider-agnostic — local Qwen with no API
keys, Anthropic, OpenAI, Bedrock, or Ollama, all behind the same `llm`
package. Nothing in `apps/` ever constructs a model; it's always
`get_chat_model()` / `get_embeddings()`. Swapping the brain doesn't touch the
grounding guarantee.

## Rendering citations a court would recognize

Cites come out in standard Connecticut form — `Conn. Gen. Stat. § 46b-82(a)`,
`Conn. Practice Book § 25-26`, `Smith v. Smith, 333 Conn. 1, 5 (2019)` — and
each links back to the retrieved passage. *[Drop the demo GIF here: click a
cite → the exact statute text that grounded it.]* That trace-back is the whole
product; everything above exists to make it true.

## What's still hard (the honest part)

- **Vector retrieval isn't user-scoped yet.** Files and projects are
  multi-tenant, but the corpus collection isn't partitioned per user — a known
  follow-up, not a solved problem.
- **Recall vs. strictness is a live tension.** "Refuse unless retrieved" means
  a too-narrow search makes the agent say "the corpus doesn't cover this" when
  it actually does. Grounded-but-silent is the safe failure for legal work, but
  it's still a failure, and tuning `k`/filters is ongoing.
- The model still writes the prose. The architecture guarantees the *sources*
  are real and clickable; it doesn't guarantee the summary is perfect. That's
  exactly why the trace-back exists — so a human checks the source, every time.

## The stack, one line

LangGraph agent · single `retrieve` tool · Postgres + pgvector · per-profile
embeddings/collections · provider-agnostic `llm` package · FastAPI · Next.js ·
AWS App Runner + private RDS. Built solo.

## Close

lawagent isn't legal advice — it's checkable legal *research* for people who
can't afford a lawyer and are representing themselves. The bet is that for
high-stakes, citation-bound domains, the winning move isn't a model that
hallucinates less — it's a system where the thing you'd get sanctioned for is
structurally hard to produce. *[Link the demo. Link the repo if open-sourcing.
Invite A2J / legaltech folks to reach out.]*

---

### Pre-publish checklist
- [ ] Confirm file/function names still match (`graph.py`, `tools.py`,
      `prompts.py`, `store.similarity_search`, `active_collection`).
- [ ] Add the demo GIF (trace-back beat) in the "Rendering citations" section.
- [ ] "Not legal advice" framing present (it is, in the close).
- [ ] No case PII / no client data in any screenshot.
- [ ] Decide repo public/private before linking it.
- [ ] Cross-post: dev blog canonical → LinkedIn (#18) → Show HN (#10) →
      r/legaltech (#11); the *Mata* opinion post (#16) links back here.
