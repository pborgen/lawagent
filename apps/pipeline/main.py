"""End-to-end case pipeline: fetch → convert → ingest.

Runs stages 1-3 of the data flow (see docs/data-flow.md) as one command,
and figures out for itself what still needs doing:

    1. fetch    efile pull       — only if the case PDFs aren't downloaded yet
    2. convert  pdf2text convert — always; it is idempotent (sha256 manifest)
    3. ingest   ingest           — only if the converted text changed since
                                   the last ingest

So the normal command is just `python -m pipeline.main run`. On a second run
with nothing new it does almost nothing. Use `--refresh` to force every stage
to re-run from scratch.

Each stage runs as its own subprocess — the same CLIs you can run by hand —
so app boundaries stay intact and each stage's own manifest/output is kept.

This covers the *private case file* stream only. The public corpus
(`ingest fetch-public`) is a separate, one-time-ish concern.

Usage:
    python -m pipeline.main run
    python -m pipeline.main run --crn 5124226
    python -m pipeline.main run --refresh        # re-pull, re-convert, re-ingest
    python -m pipeline.main run --dry-run        # ingest: chunk only, no embed
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console

from settings import get_settings


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

# apps/pipeline/main.py → parents[2] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE_FILE = ".pipeline_state.json"


def _subprocess_env() -> dict[str, str]:
    """Inherit the current env but guarantee apps/ + packages/ are importable,
    so the pipeline works whether or not the package is pip-installed."""
    env = os.environ.copy()
    extra = os.pathsep.join([str(_REPO_ROOT / "apps"), str(_REPO_ROOT / "packages")])
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{extra}{os.pathsep}{existing}" if existing else extra
    return env


def _run_stage(label: str, argv: list[str]) -> None:
    """Run one pipeline stage as a subprocess; abort the pipeline on failure."""
    console.rule(f"[bold cyan]{label}[/bold cyan]")
    console.print(f"[dim]$ {' '.join(argv)}[/dim]")
    started = time.monotonic()
    result = subprocess.run(argv, cwd=_REPO_ROOT, env=_subprocess_env())
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        console.print(
            f"[red]✗ {label} failed (exit {result.returncode}) after "
            f"{elapsed:.1f}s. Pipeline stopped.[/red]"
        )
        raise typer.Exit(code=result.returncode)
    console.print(f"[green]✓ {label} done[/green] [dim]({elapsed:.1f}s)[/dim]")


def _text_fingerprint(text_dir: Path) -> str:
    """A cheap fingerprint of the converted-text directory: path + size + mtime
    of every markdown file. Changes whenever pdf2text writes or rewrites one."""
    parts = []
    for md in sorted(text_dir.rglob("*.md")):
        st = md.stat()
        parts.append(f"{md.relative_to(text_dir)}:{st.st_size}:{st.st_mtime_ns}")
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()


@app.callback()
def _main() -> None:
    """End-to-end case pipeline: fetch → convert → ingest.

    A no-op callback — its only job is to keep `run` as an explicit
    subcommand (typer collapses single-command apps otherwise).
    """


@app.command()
def run(
    crn: str = typer.Option(
        None, help="Case reference number. Defaults to EFILE_CRN."
    ),
    collection: str = typer.Option(
        "ct-divorce", help="pgvector collection to ingest into."
    ),
    refresh: bool = typer.Option(
        False,
        help="Force every stage to re-run: re-pull, re-convert, re-ingest.",
    ),
    dry_run: bool = typer.Option(
        False,
        help="Stage 3: chunk only — do not embed, write, or update state.",
    ),
) -> None:
    """Run fetch → convert → ingest for one case, doing only what's needed."""
    crn = crn or get_settings().efile_crn or ""
    if not crn:
        console.print("[red]No CRN provided. Set EFILE_CRN or pass --crn.[/red]")
        raise typer.Exit(code=1)

    case_dir = _REPO_ROOT / "data" / "case" / "efile" / crn
    docs_dir = case_dir / "docs"
    text_dir = case_dir / "text"
    state_path = case_dir / _STATE_FILE
    py = sys.executable
    overall = time.monotonic()

    console.print(
        f"[bold]Pipeline for case {crn}[/bold] → collection '{collection}'"
        f"{'  [yellow](--refresh)[/yellow]' if refresh else ''}\n"
    )

    # ── Stage 1 — fetch ────────────────────────────────────────────────
    # Only pull from eServices when we don't already have the case PDFs.
    have_pdfs = docs_dir.is_dir() and any(docs_dir.rglob("*.pdf"))
    if have_pdfs and not refresh:
        console.print(
            "[yellow]· Stage 1 — fetch — case PDFs already downloaded, "
            "skipping (use --refresh to re-pull)[/yellow]"
        )
    else:
        _run_stage("Stage 1 — fetch (efile pull)", [
            py, "-m", "efile.main", "pull", "--crn", crn,
        ])

    # ── Stage 2 — convert ──────────────────────────────────────────────
    # Always run: pdf2text is idempotent (sha256 manifest), so this is a fast
    # no-op when nothing new was fetched.
    convert_argv = [py, "-m", "pdf2text.main", "convert", "--crn", crn]
    if refresh:
        convert_argv.append("--force")
    _run_stage("Stage 2 — convert (pdf2text)", convert_argv)

    # ── Stage 3 — ingest ───────────────────────────────────────────────
    if not text_dir.is_dir() or not any(text_dir.rglob("*.md")):
        console.print(
            f"[red]✗ Nothing to ingest: no markdown under {text_dir}.\n"
            f"  Stage 2 produced no output — does this case have documents?[/red]"
        )
        raise typer.Exit(code=1)

    fingerprint = _text_fingerprint(text_dir)
    prev_state: dict = {}
    if state_path.exists():
        try:
            prev_state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            prev_state = {}
    already_ingested = (
        not refresh
        and not dry_run
        and prev_state.get("text_fingerprint") == fingerprint
        and prev_state.get("collection") == collection
    )

    if already_ingested:
        console.print(
            "[yellow]· Stage 3 — ingest — converted text unchanged since "
            "last ingest, skipping (use --refresh to re-ingest)[/yellow]"
        )
    else:
        ingest_argv = [
            py, "-m", "ingest.main", "ingest", str(text_dir),
            "--collection", collection,
        ]
        if dry_run:
            ingest_argv.append("--dry-run")
        _run_stage("Stage 3 — ingest (chunk + embed)", ingest_argv)
        if not dry_run:
            state_path.write_text(json.dumps({
                "crn": crn,
                "collection": collection,
                "text_fingerprint": fingerprint,
                "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }, indent=2), encoding="utf-8")

    # ── Done ───────────────────────────────────────────────────────────
    console.rule("[bold green]Pipeline complete[/bold green]")
    if dry_run:
        outcome = "chunked (dry run — nothing written)"
    elif already_ingested:
        outcome = f"already up to date in '{collection}'"
    else:
        outcome = f"ingested into '{collection}'"
    console.print(
        f"[green]✓[/green] Case [bold]{crn}[/bold]: {outcome} "
        f"[dim]({time.monotonic() - overall:.1f}s total)[/dim]"
    )


if __name__ == "__main__":
    app()
