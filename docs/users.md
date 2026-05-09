# Users

## Primary user — "Author / pro se litigant" (today)

A non-lawyer going through a contested divorce in Connecticut, representing
themselves at trial. They are technically literate (a software engineer)
and willing to do real work — they don't need spoon-feeding, they need
**leverage**.

What they need from the tool:

- Translate dense CT statutes and Practice Book rules into something
  actionable for their specific case.
- Identify which statutes / rules / case law apply to a given issue
  (custody, alimony, asset division, discovery, motions practice).
- Draft starting points for documents (motions, trial briefs, exhibit
  lists, direct/cross outlines) that the user will edit and own.
- Surface the questions the user *didn't know to ask*.

What they will provide:

- Their own case facts, financial affidavit data, communications,
  prior orders.
- A growing local corpus of CT statutes, Practice Book chapters, and
  relevant CT appellate decisions.
- Feedback after each session about what was useful vs. wrong.

## Future users — "Other CT pro se divorce litigants" (later)

Once the tool works for the author, the natural expansion is other
self-represented parties in CT family court. They share the same pain
but have less technical skill — so a future v2 needs:

- A friendlier UI than a CLI / notebook.
- Guardrails against over-reliance ("this is not legal advice").
- Onboarding flows that walk a non-engineer through uploading their own
  documents safely.

This audience is **explicitly out of scope for the MVP** — but design
decisions today (data model, prompt structure, citation format) should
not paint us into a corner that blocks it.

## Explicit non-users (for now)

- Practicing family law attorneys. The tool may be useful to them, but
  they are not the design target.
- Litigants outside Connecticut. The corpus and prompts are CT-specific.
- Other practice areas (criminal, IP, etc.).
