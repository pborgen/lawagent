"""Scheduled-job daemon for lawagent.

A long-running process that hosts every recurring job in the monorepo.
Each job lives in its own file under `apps/syncd/jobs/` and registers
itself with `@sched.scheduled_job(...)` — see `jobs/s3_sync.py` for the
canonical example.

Run it:
    python -m syncd.main run
    LAWAGENT_SYNCD_S3_INTERVAL_SECONDS=60 python -m syncd.main run

What's scheduled?
    python -m syncd.main list

Intended to run as its own process (tmux pane, launchd, etc.) so it
stays alive across requests to the API.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

# Importing the jobs package triggers auto-discovery — every file in
# `jobs/` is imported, which runs its `@sched.scheduled_job(...)` decorators.
import syncd.jobs  # noqa: F401 — import has side effects (job registration)
from syncd.scheduler import sched


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.callback()
def _main() -> None:
    """Scheduled-job daemon. See `run` and `list`."""


@app.command()
def run(
    run_now: bool = typer.Option(
        True,
        "--run-now/--no-run-now",
        help="Fire every registered job once at startup, then follow the schedule.",
    ),
) -> None:
    """Start the scheduler and block until Ctrl-C."""
    jobs = sched.get_jobs()
    if not jobs:
        console.print(
            "[red]No jobs registered. Add a file under apps/syncd/jobs/.[/red]"
        )
        raise typer.Exit(code=1)

    console.print(f"[bold]Sync daemon[/bold] starting with {len(jobs)} job(s):")
    for job in jobs:
        console.print(f"  • [cyan]{job.id}[/cyan]  ({job.trigger})")
    console.print("[dim]Press Ctrl-C to stop.[/dim]\n")

    if run_now:
        # Schedule every job to fire immediately, then continue on its trigger.
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        for job in jobs:
            sched.modify_job(job.id, next_run_time=now)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]Stopped by user.[/yellow]")


@app.command("list")
def list_jobs() -> None:
    """Show every scheduled job discovered under apps/syncd/jobs/."""
    jobs = sched.get_jobs()
    if not jobs:
        console.print(
            "[yellow]No jobs registered. Add a file under apps/syncd/jobs/.[/yellow]"
        )
        return

    table = Table(title="Scheduled jobs")
    table.add_column("id", style="cyan")
    table.add_column("name")
    table.add_column("trigger")
    table.add_column("function")
    for job in jobs:
        fn = f"{job.func.__module__}.{job.func.__qualname__}"
        table.add_row(job.id, job.name or "", str(job.trigger), fn)
    console.print(table)


if __name__ == "__main__":
    app()
