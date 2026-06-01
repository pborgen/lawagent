"""Admin-only endpoints — LLM usage metering dashboard.

Every route here depends on `AdminUser`, which 403s any caller whose user
row isn't flagged `is_admin` (seeded from LAWAGENT_ADMIN_EMAILS at login).
Regular allowlisted users can't see other people's usage.

The single read endpoint returns everything the dashboard renders in one
round-trip: headline totals plus per-user, per-model, and daily-series
breakdowns over a trailing window. All aggregation happens in SQL
(`db.usage.usage_overview`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.users import AdminUser
from db import get_db_session, usage_overview
from db.usage import UsageOverview, UsageRow

router = APIRouter(prefix="/admin", tags=["admin"])


class UsageBucket(BaseModel):
    """A grouped row: one user, one model, or one day."""

    label: str
    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float

    @classmethod
    def of(cls, row: UsageRow) -> "UsageBucket":
        return cls(
            label=row.label,
            requests=row.requests,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            total_tokens=row.total_tokens,
            cost_usd=row.cost_usd,
        )


class UsageOverviewResponse(BaseModel):
    days: int
    since: datetime
    totals: UsageBucket
    by_user: list[UsageBucket]
    by_model: list[UsageBucket]
    daily: list[UsageBucket]

    @classmethod
    def of(cls, ov: UsageOverview) -> "UsageOverviewResponse":
        return cls(
            days=ov.days,
            since=ov.since,
            totals=UsageBucket.of(ov.totals),
            by_user=[UsageBucket.of(r) for r in ov.by_user],
            by_model=[UsageBucket.of(r) for r in ov.by_model],
            daily=[UsageBucket.of(r) for r in ov.daily],
        )


@router.get("/usage/overview", response_model=UsageOverviewResponse)
def usage_overview_endpoint(
    _admin: AdminUser,
    session: Annotated[Session, Depends(get_db_session)],
    days: int = Query(default=30, ge=1, le=365),
) -> UsageOverviewResponse:
    """LLM usage summary over the last `days` (default 30, max 365)."""
    return UsageOverviewResponse.of(usage_overview(session, days=days))
