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
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from llm import active_profile_name
from settings import get_settings
from store import active_collection as resolve_active_collection


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

# apps/pipeline/main.py → parents[2] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE_FILE = ".pipeline_state.json"


class Source(str, Enum):
    """Which upstream feeds Stage 1.

    `efile` — CT eServices scraper, keyed on a CRN.
    `s3`    — Mirror an S3 prefix, keyed on a derived id.
    """

    efile = "efile"
    s3 = "s3"


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


_INGESTIBLE_SUFFIXES = (".md", ".txt")


def _has_ingestible(dir_: Path) -> bool:
    return dir_.is_dir() and any(
        p.suffix.lower() in _INGESTIBLE_SUFFIXES for p in dir_.rglob("*") if p.is_file()
    )


def _text_fingerprint(text_dir: Path) -> str:
    """A cheap fingerprint of every ingestible file under `text_dir`:
    path + size + mtime. Changes whenever pdf2text writes/rewrites a .md
    or when an upstream .txt under docs/ changes."""
    parts = []
    for p in sorted(text_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in _INGESTIBLE_SUFFIXES:
            continue
        st = p.stat()
        parts.append(f"{p.relative_to(text_dir)}:{st.st_size}:{st.st_mtime_ns}")
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()


@app.callback()
def _main() -> None:
    """End-to-end case pipeline: fetch → convert → ingest.

    A no-op callback — its only job is to keep `run` as an explicit
    subcommand (typer collapses single-command apps otherwise).
    """


@app.command()
def run(
    source: Source = typer.Option(
        Source.efile,
        "--source",
        help="Which upstream feeds Stage 1: 'efile' (CT eServices) or 's3'.",
    ),
    crn: Optional[str] = typer.Option(
        None,
        help="Case reference number (efile only). Defaults to EFILE_CRN.",
    ),
    s3_uri: Optional[str] = typer.Option(
        None,
        "--s3-uri",
        help="s3://bucket/prefix/ for --source s3. Defaults to LAWAGENT_S3_URI.",
    ),
    s3_id: Optional[str] = typer.Option(
        None,
        "--s3-id",
        help="Directory name under data/case/s3/ (s3 only). "
        "Defaults to LAWAGENT_S3_ID or a slug of the prefix.",
    ),
    collection: Optional[str] = typer.Option(
        None,
        help="pgvector collection to ingest into. "
        "Defaults to the active profile's per-embeddings-model collection.",
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
    settings = get_settings()
    py = sys.executable
    overall = time.monotonic()

    # ── Per-source: resolve id, case_dir, fetch & convert commands ──────
    if source == Source.efile:
        case_id = crn or settings.efile_crn or ""
        if not case_id:
            console.print("[red]No CRN provided. Set EFILE_CRN or pass --crn.[/red]")
            raise typer.Exit(code=1)
        case_dir = _REPO_ROOT / "data" / "case" / "efile" / case_id
        fetch_argv = [py, "-m", "efile.main", "pull", "--crn", case_id]
        convert_argv = [py, "-m", "pdf2text.main", "convert", "--crn", case_id]
    else:  # Source.s3
        # Defer s3-id derivation to s3fetch so the slugging logic lives in
        # one place. We import here (not at module top) to keep boto3 off
        # the import path of efile-only runs.
        from s3fetch.src.download import resolve_target

        effective_uri = s3_uri or settings.s3_uri
        try:
            target = resolve_target(
                uri=effective_uri,
                bucket=None,
                prefix=None,
                id_=s3_id or settings.s3_id,
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        case_id = target.id
        case_dir = _REPO_ROOT / target.case_dir
        fetch_argv = [py, "-m", "s3fetch.main", "pull"]
        if s3_uri:
            fetch_argv += ["--uri", s3_uri]
        if s3_id:
            fetch_argv += ["--id", s3_id]
        convert_argv = [
            py, "-m", "pdf2text.main", "convert", "--base", str(case_dir),
        ]

    docs_dir = case_dir / "docs"
    text_dir = case_dir / "text"
    state_path = case_dir / _STATE_FILE

    # Resolve the active-profile collection up front so the state file
    # records what was actually written, and a later profile switch
    # invalidates the "already ingested" skip below.
    resolved_collection = collection or resolve_active_collection()
    profile = active_profile_name()

    console.print(
        f"[bold]Pipeline for {source.value} case {case_id}[/bold] → "
        f"collection '{resolved_collection}' (profile '{profile}')"
        f"{'  [yellow](--refresh)[/yellow]' if refresh else ''}\n"
    )

    # ── Stage 1 — fetch ────────────────────────────────────────────────
    # Skip only when docs/ already has content. For efile we look for PDFs
    # specifically (that's all eServices serves). For s3 we accept any file
    # since the bucket can contain anything.
    if source == Source.efile:
        have_content = docs_dir.is_dir() and any(docs_dir.rglob("*.pdf"))
    else:
        have_content = docs_dir.is_dir() and any(p.is_file() for p in docs_dir.rglob("*"))

    if have_content and not refresh:
        console.print(
            f"[yellow]· Stage 1 — fetch — {docs_dir} already populated, "
            f"skipping (use --refresh to re-pull)[/yellow]"
        )
    else:
        _run_stage(f"Stage 1 — fetch ({source.value} pull)", fetch_argv)

    # ── Stage 2 — convert ──────────────────────────────────────────────
    # Always run: pdf2text is idempotent (sha256 manifest), so this is a fast
    # no-op when nothing new was fetched (or when there are no PDFs at all,
    # which is allowed for the s3 source).
    if refresh:
        convert_argv = convert_argv + ["--force"]
    _run_stage("Stage 2 — convert (pdf2text)", convert_argv)

    # ── Stage 3 — ingest ───────────────────────────────────────────────
    # Prefer text/ (pdf2text output). For non-PDF s3 buckets there may be
    # nothing there, in which case fall back to docs/ — ingest's file
    # discovery picks up .md/.txt directly.
    if _has_ingestible(text_dir):
        ingest_dir: Optional[Path] = text_dir
    elif source == Source.s3 and _has_ingestible(docs_dir):
        ingest_dir = docs_dir
    else:
        ingest_dir = None

    if ingest_dir is None:
        extra = f" or under {docs_dir}" if source == Source.s3 else ""
        console.print(
            f"[red]✗ Nothing to ingest: no .md/.txt under {text_dir}{extra}.\n"
            f"  Stage 2 produced no output and the source had no text files.[/red]"
        )
        raise typer.Exit(code=1)

    fingerprint = _text_fingerprint(ingest_dir)
    prev_state: dict = {}
    if state_path.exists():
        try:
            prev_state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            prev_state = {}
    # Skip Stage 3 only when *everything* matches: text content, the
    # resolved collection name, AND the profile (and source/id). A profile
    # switch or a source switch invalidates the skip and forces a fresh
    # write. (A DB wipe with the state file intact still bypasses this —
    # use --refresh or delete the state file in that case.)
    already_ingested = (
        not refresh
        and not dry_run
        and prev_state.get("text_fingerprint") == fingerprint
        and prev_state.get("collection") == resolved_collection
        and prev_state.get("profile") == profile
        and prev_state.get("source") == source.value
        and prev_state.get("id") == case_id
    )

    if already_ingested:
        console.print(
            "[yellow]· Stage 3 — ingest — converted text unchanged since "
            "last ingest under this profile, skipping (use --refresh to "
            "re-ingest)[/yellow]"
        )
    else:
        ingest_argv = [
            py, "-m", "ingest.main", "ingest", str(ingest_dir),
            "--collection", resolved_collection,
        ]
        if dry_run:
            ingest_argv.append("--dry-run")
        _run_stage("Stage 3 — ingest (chunk + embed)", ingest_argv)
        if not dry_run:
            state_path.write_text(json.dumps({
                "source": source.value,
                "id": case_id,
                "profile": profile,
                "collection": resolved_collection,
                "text_fingerprint": fingerprint,
                "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }, indent=2), encoding="utf-8")

    # ── Done ───────────────────────────────────────────────────────────
    console.rule("[bold green]Pipeline complete[/bold green]")
    if dry_run:
        outcome = "chunked (dry run — nothing written)"
    elif already_ingested:
        outcome = f"already up to date in '{resolved_collection}'"
    else:
        outcome = f"ingested into '{resolved_collection}'"
    console.print(
        f"[green]✓[/green] {source.value} case [bold]{case_id}[/bold]: {outcome} "
        f"[dim]({time.monotonic() - overall:.1f}s total)[/dim]"
    )


if __name__ == "__main__":
    app()
