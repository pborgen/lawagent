"""Thin CLI for the ingestion pipeline.

The actual work lives in `packages/ingestion`. This file exists only
to give ingestion its own runnable entrypoint, separate from the agent.

Usage:
    python -m ingest.main data/raw/
    python -m ingest.main data/raw/cgs-46b-82.txt --collection ct-divorce
"""
from __future__ import annotations

import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from ingestion import discover_files, write_to_chroma
from ingestion.chunking import chunk_file


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def ingest(
    source: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=True),
    collection: str = typer.Option("ct-divorce", help="Chroma collection name."),
    persist_dir: Path = typer.Option(
        None, help="Override LAWAGENT_VECTORSTORE_DIR for this run."
    ),
) -> None:
    load_dotenv()

    files = discover_files(source)
    if not files:
        console.print(f"[yellow]No .txt/.md files found under {source}.[/yellow]")
        sys.exit(1)

    chunks = []
    for f in files:
        file_chunks = chunk_file(f)
        chunks.extend(file_chunks)
        rel = f.relative_to(source) if source.is_dir() else f.name
        console.print(
            f"  chunked [cyan]{rel}[/cyan] → {len(file_chunks)} chunks "
            f"([dim]{file_chunks[0].metadata.source_type.value}[/dim])"
        )

    if not chunks:
        console.print("[yellow]No chunks produced.[/yellow]")
        sys.exit(1)

    console.print(f"\nEmbedding [bold]{len(chunks)}[/bold] chunks…")
    write_to_chroma(chunks, collection=collection, persist_dir=persist_dir)
    console.print(
        f"[green]✓[/green] Ingested {len(chunks)} chunks from {len(files)} files "
        f"into [bold]{collection}[/bold]"
    )


if __name__ == "__main__":
    app()
