"""Persist and aggregate LLM usage events.

Write path: `record_usage_events()` turns the in-memory `UsageEvent`s
from `llm.usage` into `LlmUsageEvent` rows, pricing each one at write time
(`llm.cost_usd`) so historical totals never move when list prices change.

Read path: `usage_overview()` is the single query the admin dashboard
needs — headline totals plus per-user, per-model, and daily-series
breakdowns, all scoped to a trailing window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import LlmUsageEvent, User
from llm import UsageEvent, cost_usd


def record_usage_events(
    session: Session,
    *,
    events: Iterable[UsageEvent],
    user_sub: Optional[str] = None,
    project_id=None,
    mode: Optional[str] = None,
) -> int:
    """Insert one `LlmUsageEvent` row per `UsageEvent`. Returns the count.

    Skips fully empty chat events (a model that reported nothing) so we
    don't clutter the table with zero-token rows. Commits on success; the
    caller decides how to handle failure (the /chat route swallows it so
    metering can never break a chat).
    """
    rows: list[LlmUsageEvent] = []
    for ev in events:
        if ev.total_tokens == 0 and ev.kind == "chat":
            continue
        rows.append(
            LlmUsageEvent(
                user_sub=user_sub,
                project_id=project_id,
                kind=ev.kind,
                provider=ev.provider,
                model=ev.model,
                input_tokens=ev.input_tokens,
                output_tokens=ev.output_tokens,
                total_tokens=ev.total_tokens,
                tokens_estimated=ev.tokens_estimated,
                cost_usd=cost_usd(ev.model, ev.input_tokens, ev.output_tokens),
                mode=mode if ev.kind == "chat" else None,
            )
        )
    if not rows:
        return 0
    session.add_all(rows)
    session.commit()
    return len(rows)


# --- Aggregation (admin dashboard) --------------------------------------


@dataclass
class UsageRow:
    """One grouped bucket: a user, a model, or a day."""

    label: str
    requests: int  # distinct chat calls in the bucket
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


@dataclass
class UsageOverview:
    days: int
    since: datetime
    totals: UsageRow
    by_user: list[UsageRow]
    by_model: list[UsageRow]
    daily: list[UsageRow]


_FLOAT0 = 0.0


def _to_float(value: Optional[Decimal]) -> float:
    return float(value) if value is not None else _FLOAT0


def usage_overview(session: Session, *, days: int = 30) -> UsageOverview:
    """Summarize the last `days` of usage for the admin dashboard.

    "requests" counts chat events only (one per /chat call); token and
    cost sums include embeddings. Grouping happens in SQL so this stays a
    handful of round-trips regardless of table size.
    """
    days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Reusable aggregate column expressions.
    requests = func.count().filter(LlmUsageEvent.kind == "chat")
    in_tok = func.coalesce(func.sum(LlmUsageEvent.input_tokens), 0)
    out_tok = func.coalesce(func.sum(LlmUsageEvent.output_tokens), 0)
    tot_tok = func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0)
    cost = func.coalesce(func.sum(LlmUsageEvent.cost_usd), 0)
    where = LlmUsageEvent.created_at >= since

    # Headline totals.
    totals_row = session.execute(
        select(requests, in_tok, out_tok, tot_tok, cost).where(where)
    ).one()
    totals = UsageRow(
        label="all",
        requests=int(totals_row[0] or 0),
        input_tokens=int(totals_row[1]),
        output_tokens=int(totals_row[2]),
        total_tokens=int(totals_row[3]),
        cost_usd=_to_float(totals_row[4]),
    )

    # Per user (joined to email for a human-readable label).
    by_user_rows = session.execute(
        select(
            func.coalesce(User.email, LlmUsageEvent.user_sub, "unknown"),
            requests,
            in_tok,
            out_tok,
            tot_tok,
            cost,
        )
        .select_from(LlmUsageEvent)
        .join(User, User.cognito_sub == LlmUsageEvent.user_sub, isouter=True)
        .where(where)
        .group_by(LlmUsageEvent.user_sub, User.email)
        .order_by(cost.desc())
    ).all()

    # Per model.
    by_model_rows = session.execute(
        select(LlmUsageEvent.model, requests, in_tok, out_tok, tot_tok, cost)
        .where(where)
        .group_by(LlmUsageEvent.model)
        .order_by(cost.desc())
    ).all()

    # Daily series (UTC calendar day), oldest first for charting.
    day = func.date(LlmUsageEvent.created_at)
    daily_rows = session.execute(
        select(day, requests, in_tok, out_tok, tot_tok, cost)
        .where(where)
        .group_by(day)
        .order_by(day.asc())
    ).all()

    def _rows(records) -> list[UsageRow]:
        return [
            UsageRow(
                label=str(r[0]),
                requests=int(r[1] or 0),
                input_tokens=int(r[2]),
                output_tokens=int(r[3]),
                total_tokens=int(r[4]),
                cost_usd=_to_float(r[5]),
            )
            for r in records
        ]

    return UsageOverview(
        days=days,
        since=since,
        totals=totals,
        by_user=_rows(by_user_rows),
        by_model=_rows(by_model_rows),
        daily=_rows(daily_rows),
    )
