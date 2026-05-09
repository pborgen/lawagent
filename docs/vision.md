# Vision

## Problem

A pro se litigant in a Connecticut divorce has to learn a lot of unfamiliar
law — Connecticut General Statutes Title 46b (Family Law), the Connecticut
Practice Book (especially Chs. 25 / 25a on family matters), local court
rules, and the substantive doctrine the judge will apply (custody best
interest factors, alimony factors, equitable distribution). Existing
options are bad:

- Hiring a lawyer for every question is expensive.
- Reading raw statutes is slow and easy to misread without context.
- General-purpose LLMs hallucinate citations and are not grounded in CT law.
- Self-help books are static and don't reason over your specific facts.

## What we're building

An **agentic trial-prep assistant** that helps a pro se litigant
understand and apply Connecticut divorce law to their own case. The user
gives it a question, a statute to interpret, or a fact pattern; the agent
researches over a curated CT-divorce corpus and produces a grounded,
cited answer in the format the user needs at that moment.

## Value proposition

- **Grounded:** every claim cites the underlying CT statute, rule, or case.
- **Specific to CT divorce:** the corpus and prompts are tuned to family
  law in Connecticut, not generic US law.
- **Multi-format output:** memo, short answer, or annotated statute view —
  whichever fits the task.

## Non-goals

- Not legal advice. The tool helps the user think; it does not replace a
  lawyer and does not promise correctness.
- Not a generalist legal research tool. CT divorce is the wedge.
- Not a courtroom-automation product (no e-filing, no docket scraping
  in the MVP).

## North-star use case

> "I have a hearing on a motion for pendente lite alimony in three weeks.
> Help me understand what the judge will weigh, what evidence I need to
> bring, and draft an outline of my argument grounded in CGS § 46b-83
> and the relevant case law."
