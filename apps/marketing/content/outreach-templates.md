# Outreach templates

Reusable, organic, no-spend outreach for ideas #6 (LawSites pitch), #7
(Artificial Lawyer), #22 (warm emails to A2J/clinics), #23 (founder DMs), and
#9 (podcast). Fill the `{{placeholders}}` from [targets.md](../targets.md).

Ground rules for all of them:
- **Short.** 5–8 sentences max. Busy people. One clear ask.
- **Lead with the wedge, not the résumé:** anti-hallucination / checkable
  citations, *Mata v. Avianca* as the shared reference point.
- **Always include the 90s demo link** (the trace-back beat). Show, don't tell.
- **"Not legal advice / for self-represented people"** appears once — with this
  audience it's a trust signal.
- **One ask per message.** Reply, 15-min call, or "would you cover it?" — pick one.
- Never attach the case file or anything from `data/`. Demo uses generic data.

---

## 1. Legaltech blog pitch — LawSites / Artificial Lawyer (ideas #6, #7)

**Subject:** A legal assistant that structurally can't fake a citation

> Hi {{name}},
>
> After *Mata v. Avianca*, the usual reaction was "AI isn't ready for law." I
> took the opposite bet and built {{product}} — a research assistant for people
> representing themselves in Connecticut divorce cases — around one rule: every
> citation traces back to the exact retrieved source text, and the clickable
> links are minted from document metadata, not the model's output. A fabricated
> case literally can't get a working link.
>
> 90-second demo (no audio): {{demo_url}}. It's checkable legal *research*, not
> legal advice — aimed at self-represented litigants who can't afford counsel.
> Built solo: LangGraph + pgvector, provider-agnostic.
>
> Thought it might fit {{outlet}}'s coverage of A2J / legal-AI grounding. Happy
> to send a written walkthrough or hop on a quick call — whatever's easiest. No
> worries if it's not a fit.
>
> Thanks,
> Paul

*Variant for Artificial Lawyer:* swap the middle line to emphasize the RAG
architecture (retrieve→reason→cite, per-profile pgvector collections) — that
outlet leans technical.

---

## 2. A2J org / legal-aid / clinic warm email (idea #22)

**Subject:** Free citation-checked research tool for self-represented litigants

> Hi {{name}},
>
> I'm a pro se litigant who got tired of AI tools that invent case citations,
> so I built {{product}} to fix it: it answers Connecticut family-law questions
> only from real retrieved authorities, and every claim links back to the
> source statute or case so a non-lawyer can verify it. It's not legal advice —
> it's research the litigant can check themselves.
>
> Because {{org}} works directly with self-represented people, I'd love your
> read on whether this is actually useful — and what would make it more so.
> 90-second demo: {{demo_url}}.
>
> Could I get 15 minutes, or send it to whoever runs your self-help / tech
> work? Either way, thank you for what {{org}} does.
>
> Paul

---

## 3. Legaltech / A2J founder DM (idea #23)

> Hi {{name}} — really like what you're building with {{their_thing}}. I built
> a small thing in an adjacent lane: a pro-se legal research agent where
> citations structurally can't be hallucinated (links come from retrieved
> chunk metadata, not the LLM). 90s demo: {{demo_url}}. Not pitching anything —
> curious if you've hit the grounding/recall trade-off too, and open to compare
> notes.

---

## 4. Podcast pitch (idea #9)

**Subject:** Guest idea — the *Mata v. Avianca* problem is solvable in architecture

> Hi {{name}},
>
> Possible angle for {{podcast}}: I'm a self-represented litigant who built a
> legal research agent designed so hallucinated citations are structurally
> hard to produce — and there's a real story in building it solo, for my own
> divorce case, as access-to-justice tooling. Demo: {{demo_url}}.
>
> Happy to come on and show the trace-back live, talk RAG grounding, and the
> A2J angle. Would that fit an upcoming episode?
>
> Paul

---

## 5. Follow-up (any of the above, once, after ~5–7 days)

> Hi {{name}} — circling back once in case this slipped by. Same 90s demo:
> {{demo_url}}. Totally fine if it's not a fit; I won't keep nudging. Thanks!

---

## Sending discipline
- Personalize the first sentence of every message (reference their actual
  work). Generic = ignored.
- One follow-up, then stop.
- Track sends in a simple list: target · channel · date sent · reply · outcome.
- Batch to ~5–10 at a time so you can keep each one personal (idea #22 is
  literally "10 warm emails").
