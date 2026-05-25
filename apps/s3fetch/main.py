"""Pull case documents from an S3 prefix.

Mirrors the layout of `apps/efile`: this app only downloads (and writes
a manifest); ingestion into pgvector is a separate step.

Usage:
    python -m s3fetch.main pull
    python -m s3fetch.main pull --uri s3://my-bucket/case/5124226/
    python -m s3fetch.main pull --bucket my-bucket --prefix case/5124226/
    python -m s3fetch.main pull --uri s3://b/p/ --id my-case-slug

Defaults:
    --uri    → LAWAGENT_S3_URI in your .env
    --id     → LAWAGENT_S3_ID  in your .env (otherwise derived from the prefix)

AWS credentials and region come from the standard chain (env vars,
~/.aws/credentials, instance role) — same as the `bedrock` profile.
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from s3fetch.src.download import S3Target, pull, resolve_target
from settings import get_settings


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.callback()
def _main() -> None:
    """S3 fetcher.

    No-op callback — keeps `pull` as an explicit subcommand (Typer
    collapses single-command apps otherwise).
    """


@app.command("pull")
def pull_cmd(
    uri: Optional[str] = typer.Option(
        None,
        help="s3://bucket/prefix/ — overrides LAWAGENT_S3_URI.",
    ),
    bucket: Optional[str] = typer.Option(
        None,
        help="Bucket name (use with --prefix as an alternative to --uri).",
    ),
    prefix: Optional[str] = typer.Option(
        None, help="Key prefix to mirror. Empty = whole bucket."
    ),
    id_: Optional[str] = typer.Option(
        None,
        "--id",
        help="Override the directory name under data/case/s3/. "
        "Defaults to LAWAGENT_S3_ID, else the last prefix segment "
        "(or the bucket name).",
    ),
) -> None:
    """Mirror an S3 prefix into data/case/s3/<id>/docs/."""
    settings = get_settings()
    effective_uri = uri or settings.s3_uri
    effective_id = id_ or settings.s3_id
    try:
        target: S3Target = resolve_target(
            uri=effective_uri, bucket=bucket, prefix=prefix, id_=effective_id
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    console.print(
        f"Pulling [bold]s3://{target.bucket}/{target.prefix}[/bold] "
        f"→ {target.case_dir}"
    )

    try:
        manifest = pull(target)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    counts = manifest.get("counts", {})
    console.print(
        f"[green]✓[/green] Done. "
        f"new={counts.get('new_downloads', 0)}, "
        f"skipped={counts.get('skipped_already_present', 0)}, "
        f"deleted={counts.get('deleted', 0)}, "
        f"total={counts.get('total_objects', 0)}"
    )
    console.print(f"Manifest: {target.case_dir / 'manifest.json'}")
    console.print(
        f"To convert any PDFs and ingest, run:\n"
        f"  [cyan]python -m pdf2text.main convert --base {target.case_dir}[/cyan]\n"
        f"  [cyan]python -m ingest.main {target.case_dir / 'text'}[/cyan]\n"
        f"Or, for text/markdown files that need no conversion:\n"
        f"  [cyan]python -m ingest.main {target.case_dir / 'docs'}[/cyan]"
    )


if __name__ == "__main__":
    app()
