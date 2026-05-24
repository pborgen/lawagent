"""PDF -> markdown + JSON converter for the RAG pipeline.

Walks a CRN's efile docs directory, converts every new PDF into a
markdown file (RAG-ingestable) plus a JSON sidecar (per-page text +
provenance), and tracks what's been processed in pdf2text_manifest.json
keyed by source SHA-256. Re-runs are idempotent.

Usage:
    python -m pdf2text.main convert                  # uses EFILE_CRN
    python -m pdf2text.main convert --crn 5124226
    python -m pdf2text.main convert --crn 5124226 --force
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from pdf2text.src.extract import extract_pdf, sha256, to_markdown, to_sidecar
from settings import get_settings


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _case_dir(crn: str) -> Path:
    return Path("data/case/efile") / crn


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _previous_by_sha(manifest: dict) -> dict[str, dict]:
    return {d["source_sha256"]: d for d in manifest.get("documents", [])}


@app.callback()
def _main() -> None:
    """PDF → markdown converter.

    No-op callback — keeps `convert` as an explicit subcommand (Typer
    collapses single-command apps otherwise).
    """


@app.command()
def convert(
    crn: str = typer.Option(None, help="Case reference number. Defaults to EFILE_CRN."),
    base_dir: Optional[Path] = typer.Option(
        None,
        "--base",
        help="Case directory to convert (must contain a docs/ subdir). "
        "Mutually exclusive with --crn; use this for non-efile sources "
        "like data/case/s3/<id>.",
    ),
    force: bool = typer.Option(False, help="Re-convert PDFs even if already in the manifest."),
) -> None:
    """Convert every PDF under <base>/docs/ to markdown + JSON."""
    if base_dir is not None and crn:
        console.print("[red]Pass --crn OR --base, not both.[/red]")
        raise typer.Exit(code=1)
    if base_dir is not None:
        base = base_dir
    else:
        crn = crn or get_settings().efile_crn or ""
        if not crn:
            console.print(
                "[red]No CRN or --base provided. Set EFILE_CRN, pass --crn, or pass --base.[/red]"
            )
            raise typer.Exit(code=1)
        base = _case_dir(crn)

    docs_dir = base / "docs"
    text_dir = base / "text"
    if not docs_dir.exists():
        console.print(
            f"[red]No docs dir at {docs_dir}. "
            "Run the matching fetch step first (e.g. efile pull / s3fetch pull).[/red]"
        )
        raise typer.Exit(code=1)
    text_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = base / "pdf2text_manifest.json"
    prev_manifest = _load_manifest(manifest_path)
    prev_by_sha = {} if force else _previous_by_sha(prev_manifest)

    documents: list[dict] = []
    new_count = 0
    skipped_count = 0

    pdfs = sorted(docs_dir.rglob("*.pdf"))
    for pdf in pdfs:
        rel_pdf = str(pdf.relative_to(base))
        digest = sha256(pdf)
        cached = prev_by_sha.get(digest)
        if cached and (base / cached["markdown_path"]).exists():
            documents.append(cached)
            skipped_count += 1
            continue

        console.print(f"Converting [bold]{rel_pdf}[/bold]")
        result = extract_pdf(pdf)

        stem = pdf.stem
        md_path = text_dir / f"{stem}.md"
        json_path = text_dir / f"{stem}.json"
        md_path.write_text(to_markdown(result), encoding="utf-8")
        sidecar = to_sidecar(result, source_rel=rel_pdf)
        json_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

        documents.append({
            "source_pdf": rel_pdf,
            "source_sha256": digest,
            "markdown_path": str(md_path.relative_to(base)),
            "json_path": str(json_path.relative_to(base)),
            "page_count": result.page_count,
            "ocr_used": result.ocr_used,
            "converted_at": sidecar["converted_at"],
        })
        new_count += 1

    manifest = {
        "crn": crn,
        "last_run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "documents": documents,
        "counts": {
            "newly_converted": new_count,
            "skipped_already_present": skipped_count,
            "total_pdfs": len(pdfs),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    console.print(
        f"[green]✓[/green] Done. "
        f"converted={new_count}, skipped={skipped_count}, total={len(pdfs)}"
    )
    console.print(f"Manifest: {manifest_path}")
    console.print(
        f"To ingest the markdown into pgvector, run:\n"
        f"  [cyan]python -m ingest.main {text_dir}[/cyan]"
    )


if __name__ == "__main__":
    app()
