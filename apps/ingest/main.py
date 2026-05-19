"""Thin CLI for the ingestion pipeline.

The actual work lives in `packages/ingestion`. This file exists only
to give ingestion its own runnable entrypoint, separate from the agent.

Usage:
    python -m ingest.main fetch-public
    python -m ingest.main fetch-public --no-pdf
    python -m ingest.main data/raw/
    python -m ingest.main data/raw/cgs-46b-82.txt --collection ct-divorce
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ingestion import discover_files
from ingestion.chunking import chunk_file
from store import active_collection, write_chunks
from ingest.src.fetch_public import fetch_public_starter


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()
_KNOWN_COMMANDS = {"fetch-public", "ingest"}
_ROOT_FLAGS = {"--help", "-h", "--show-completion", "--install-completion"}


@app.command("fetch-public")
def fetch_public(
    out_dir: Path = typer.Option(
        Path("data/raw/public"),
        help="Directory to write fetched public-source files into.",
    ),
    force: bool = typer.Option(
        False,
        help="Overwrite files that already exist in the output directory.",
    ),
    pdf: bool = typer.Option(
        True,
        "--pdf/--no-pdf",
        help="Include PDF-based sources like Judicial Branch forms and guides.",
    ),
    statutes: bool = typer.Option(
        True,
        "--statutes/--no-statutes",
        help="Include Connecticut statute sources.",
    ),
    guides: bool = typer.Option(
        True,
        "--guides/--no-guides",
        help="Include Judicial Branch guides and law-library materials.",
    ),
    forms: bool = typer.Option(
        True,
        "--forms/--no-forms",
        help="Include official Judicial Branch form PDFs.",
    ),
) -> None:
    """Fetch a starter set of official CT divorce sources into data/raw/."""
    manifest = fetch_public_starter(
        out_dir=out_dir,
        force=force,
        include_statutes=statutes,
        include_guides=guides,
        include_forms=forms,
        include_pdfs=pdf,
        console=console,
    )
    counts = manifest["counts"]
    console.print(
        f"[green]✓[/green] Public corpus ready. "
        f"fetched={counts['fetched']}, skipped={counts['skipped']}, "
        f"failed={counts['failed']}, total={counts['total']}"
    )
    console.print(
        f"Next:\n"
        f"  [cyan]python -m ingest.main {out_dir} --dry-run[/cyan]\n"
        f"  [cyan]python -m ingest.main {out_dir}[/cyan]"
    )


@app.command()
def ingest(
    source: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=True),
    collection: Optional[str] = typer.Option(
        None,
        help="pgvector collection name. Defaults to the active profile's collection.",
    ),
    connection: str = typer.Option(
        None,
        help="Override LAWAGENT_PG_URL for this run "
        "(e.g. postgresql+psycopg://user:pw@host:5432/db).",
    ),
    dry_run: bool = typer.Option(
        False,
        help="Parse and chunk files without embedding or writing to the vector store.",
    ),
) -> None:
    files = discover_files(source)
    if not files:
        console.print(f"[yellow]No .txt/.md files found under {source}.[/yellow]")
        sys.exit(1)

    chunks = []
    for f in files:
        file_chunks = chunk_file(f)
        chunks.extend(file_chunks)
        rel = f.relative_to(source) if source.is_dir() else f.name
        if not file_chunks:
            console.print(f"  skipped [yellow]{rel}[/yellow] (no chunks produced)")
            continue

        sample = file_chunks[0].metadata
        console.print(
            f"  chunked [cyan]{rel}[/cyan] → {len(file_chunks)} chunks "
            f"([dim]{sample.source_type.value} / {sample.authority_level.value}[/dim])"
        )

    if not chunks:
        console.print("[yellow]No chunks produced.[/yellow]")
        sys.exit(1)

    if dry_run:
        console.print(
            f"\n[green]✓[/green] Parsed {len(files)} files into "
            f"[bold]{len(chunks)}[/bold] chunks (dry run)"
        )
        return

    target = collection or active_collection()
    console.print(f"\nEmbedding [bold]{len(chunks)}[/bold] chunks…")
    write_chunks(chunks, collection=target, connection=connection)
    console.print(
        f"[green]✓[/green] Ingested {len(chunks)} chunks from {len(files)} files "
        f"into [bold]{target}[/bold]"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] not in _KNOWN_COMMANDS | _ROOT_FLAGS:
        sys.argv.insert(1, "ingest")
    app()
