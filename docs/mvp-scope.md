# MVP Scope

The MVP exists to answer one question: **can a LangChain agent, grounded
in a curated CT-divorce corpus in a vector DB, produce trial-prep output
that's actually useful to the author's own case?**

If yes → keep building toward a tool other pro se parties could use.
If no → learn why before investing more.

**Hard constraint:** the author has a divorce trial within 4 weeks of
2026-05-09 (target: ~2026-06-06). The MVP must be usable for that
trial. **Initial focus is alimony** (CGS §§ 46b-82, 46b-83). Other
issues (custody, asset division) are explicitly v0.2.

## In scope

### Corpus (alimony-focused for v0)
- **CGS § 46b-82** (alimony — final orders, factors).
- **CGS § 46b-83** (pendente lite alimony).
- Surrounding sections that interact with alimony (e.g. § 46b-86
  modification, § 46b-87 contempt) — at least the text, even if not
  the focus.
- 10–20 CT appellate decisions interpreting §§ 46b-82 / 46b-83,
  hand-picked.
- CT Practice Book Ch. 25 sections relevant to alimony motions and
  evidence.
- The author's own case documents (pleadings, financial affidavits,
  prior orders) — kept separate from the public corpus, in
  gitignored `data/case/`.

Other parts of CGS Title 46b and other Practice Book chapters can be
ingested later but are not on the critical path for trial.

### Capabilities
- Ingest documents into a local vector DB with chunking, metadata
  (citation, jurisdiction, document type, date), and embeddings.
- Agentic retrieval: agent decides what to search for, retrieves
  passages, reasons, and possibly searches again before answering.
- Three output modes:
  - **Memo:** Issue / Rule / Analysis / Conclusion with pinpoint cites.
  - **Short answer:** direct answer + supporting passages.
  - **Annotated statute view:** the statute text with the agent's notes
    overlaid for the user's facts.
- Every claim must carry a citation back to a source chunk in the corpus.

### Inputs the agent accepts
- A research question ("What are the alimony factors under CGS 46b-82?")
- A statute or rule reference to interpret
- A fact pattern + a question grounded in those facts
- A document the user wants help understanding or critiquing

### Surface
- CLI / notebook is fine for v0. No web UI.
- Single user, local machine.

## Out of scope (for the MVP)

- Multi-user / cloud deployment.
- Federal or non-CT state law.
- Practice areas other than family law / divorce.
- E-filing, docket integration, calendar/deadline tracking.
- Document drafting beyond outlines and starting points.
- Any "predict outcome" or "estimate alimony amount" style features —
  too easy to be wrong in ways that hurt the user.
- Friendly UI for non-technical users (deferred to v2).

## Definition of done (MVP)

The author can sit down with a real upcoming hearing or motion in their
own case and:

1. Ask the agent a focused question about CT divorce law.
2. Get back an answer with **valid, checkable citations** to specific
   CGS sections, Practice Book rules, or CT appellate cases.
3. Receive output in whichever of the three modes was requested.
4. Trust the answer enough to use it as a starting point — meaning
   citation accuracy and groundedness are good enough that verifying
   takes minutes, not hours.

If verifying takes longer than just doing the research yourself, the
MVP failed.
