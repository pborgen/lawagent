"""Periodic S3 → pgvector sync.

Re-runs the case pipeline (s3fetch → pdf2text → ingest) every few minutes
so files uploaded to the bucket from the web UI become searchable by the
agent without any manual step. Every pipeline stage is idempotent, so a
no-change tick is cheap (one list_objects_v2 + manifest compare).

Tune the cadence with `LAWAGENT_SYNCD_S3_INTERVAL_SECONDS` (default 300).
"""
from __future__ import annotations

import os
import time

from rich.console import Console

from pipeline.main import Source, run as pipeline_run
from syncd.scheduler import sched


console = Console()

_INTERVAL = int(os.environ.get("LAWAGENT_SYNCD_S3_INTERVAL_SECONDS", "300"))


@sched.scheduled_job(
    "interval",
    seconds=_INTERVAL,
    id="s3_sync",
    name="S3 → pgvector sync",
    max_instances=1,        # never overlap a long tick with the next one
    coalesce=True,          # if the daemon was paused, only run once on resume
    next_run_time=None,     # kicked off manually on startup by main.py
)
def s3_sync() -> None:
    """One sync tick — let pipeline.run figure out what (if anything) changed."""
    started = time.monotonic()
    try:
        pipeline_run(
            source=Source.s3,
            crn=None,
            s3_uri=None,
            s3_id=None,
            collection=None,
            refresh=False,
            dry_run=False,
        )
    except SystemExit as exc:
        # typer.Exit subclasses SystemExit; swallow so the scheduler keeps ticking.
        console.print(
            f"[red]✗ s3_sync exited early (code {exc.code}). Will retry next tick.[/red]"
        )
    except Exception as exc:  # noqa: BLE001 - daemon must survive surprises
        console.print(f"[red]✗ s3_sync crashed: {exc!r}. Will retry next tick.[/red]")
    else:
        console.print(
            f"[dim]s3_sync tick finished in {time.monotonic() - started:.1f}s.[/dim]"
        )
