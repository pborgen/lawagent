# lawagent — Requirements

A trial-prep assistant for a pro se litigant in a Connecticut divorce.
Built for one user (the author) first; designed so it can later help
other self-represented divorce parties.

These are living docs; expect them to change as the concept sharpens.

## Index

- [vision.md](vision.md) — what the product is and why it exists
- [users.md](users.md) — primary user (now) and future users (later)
- [mvp-scope.md](mvp-scope.md) — first version: in / out
- [architecture.md](architecture.md) — monorepo layout, LangChain, vector DB
- [corpus-format.md](corpus-format.md) — raw source conventions and chunking rules
- [open-questions.md](open-questions.md) — decisions still pending
- [spike-plan.md](spike-plan.md) — first prototype to validate the core loop

## Status

- **Stage:** scaffolding the monorepo
- **Trial:** within 4 weeks of 2026-05-09 (i.e. by ~2026-06-06)
- **Initial focus area:** alimony (CGS §§ 46b-82, 46b-83)
- **Stack:** Python monorepo, LangChain + LangGraph, pgvector on
  Postgres (local Docker or Aurora/RDS), Claude, hosted embeddings
  (Voyage default)
- **Last updated:** 2026-05-09
