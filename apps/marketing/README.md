# apps/marketing

Standalone workspace for the **advertising / go-to-market initiative**. Kept
separate from product code on purpose: nothing here is imported by the agent,
API, or web app. It holds the *plan*, the *ideas*, the *target list*, and the
*content drafts* for promoting lawagent.

> **Audience:** the legal / startup community — access-to-justice (A2J) orgs,
> legaltech founders & builders, attorneys who could refer, investors.
> **Budget:** organic only (time, no ad spend).
> **Positioning wedge:** *grounded, checkable citations* — the
> anti-hallucination legal assistant. (Direct answer to the *Mata v. Avianca*
> fake-citation anxiety this audience has.)

## Layout

```
plan.md                 the 5-phase GTM plan (positioning → ideate → score → assets → cadence → measure)
ideas.md                ~30 ideas across 6 channel buckets, scored & ranked
targets.md              named orgs / blogs / conferences / submission links  (research output)
content/
  flagship-post.md      "How I built a legal assistant that can't hallucinate citations"
  demo-script.md        60–90s demo video script (the universal reusable asset)
  outreach-templates.md warm-email / DM templates for A2J + legaltech outreach
```

## Compliance note (flagged, not dwelt on)

Every public asset shows the **"not legal advice / tool for self-represented
people"** framing. With the A2J audience this is a *trust signal*, not a
disclaimer tax. Avoid any claim that the tool gives legal advice.

## Status

- [x] Plan drafted (`plan.md`)
- [x] Ideas generated + ranked (`ideas.md`)
- [x] Target list researched (`targets.md`) — verified, link-backed (2026-06-01)
- [x] Demo video scripted (`content/demo-script.md`) — not yet recorded
- [x] Flagship post drafted (`content/flagship-post.md`) — grounded in real code; needs GIF + publish pass
- [x] Outreach templates (`content/outreach-templates.md`)

## Fire order (when assets are live)
1. Record the demo (`content/demo-script.md`) + publish flagship post.
2. **Easy wins:** Legaltech Hub free listing; Stanford AI+A2J Google Form.
3. **Pitches:** LawSites/LawNext, Artificial Lawyer (richard@artificiallawyer.com),
   Talk Justice guest form — using `content/outreach-templates.md`.
4. **Launch:** Show HN → r/legaltech → LinkedIn. Then Product Hunt.
5. **Local/long-game:** CTLawHelp partnership outreach; watch ITC27 CFP.
