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

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from corpus import get_state
from ingestion import discover_files
from ingestion.chunking import chunk_file
from store import (
    active_collection,
    collection_for,
    delete_chunks_by_source_paths,
    list_source_paths_under,
    write_chunks,
)
from ingest.src.fetch_public import fetch_public_starter
from ingest.src.official_al import crawl as crawl_al
from ingest.src.official_az import crawl as crawl_az
from ingest.src.official_hi import crawl as crawl_hi
from ingest.src.official_il import crawl as crawl_il
from ingest.src.official_ia import crawl as crawl_ia
from ingest.src.official_id import crawl as crawl_id
from ingest.src.official_in import crawl as crawl_in
from ingest.src.official_ks import crawl as crawl_ks
from ingest.src.official_ky import crawl as crawl_ky
from ingest.src.official_la import crawl as crawl_la
from ingest.src.official_ma import crawl as crawl_ma
from ingest.src.official_md import crawl as crawl_md
from ingest.src.official_mi import crawl as crawl_mi
from ingest.src.official_mn import crawl as crawl_mn
from ingest.src.official_mo import crawl as crawl_mo
from ingest.src.official_nc import crawl as crawl_nc
from ingest.src.official_ne import crawl as crawl_ne
from ingest.src.official_nm import crawl as crawl_nm
from ingest.src.official_oh import crawl as crawl_oh
from ingest.src.official_ok import crawl as crawl_ok
from ingest.src.official_pa import crawl as crawl_pa
from ingest.src.official_sc import crawl as crawl_sc
from ingest.src.official_va import crawl as crawl_va
from ingest.src.official_wa import crawl as crawl_wa
from ingest.src.official_wi import crawl as crawl_wi
from ingest.src.official_wv import crawl as crawl_wv
from ingest.src.official_de import crawl as crawl_de
from ingest.src.official_me import crawl as crawl_me
from ingest.src.official_mt import crawl as crawl_mt
from ingest.src.official_nh import crawl as crawl_nh
from ingest.src.official_ri import crawl as crawl_ri
from ingest.src.official_sd import crawl as crawl_sd
from ingest.src.official_ak import crawl as crawl_ak
from ingest.src.official_nd import crawl as crawl_nd
from ingest.src.official_vt import crawl as crawl_vt
from ingest.src.official_wy import crawl as crawl_wy
from ingest.src.public_law import crawl_public_law, fetch_specs
from ingest.src.public_law_flat import crawl_public_law_flat
from ingest.src.public_law_tx import crawl_public_law_tx

# Maps a statute code's `layout` to the crawler that handles that public.law
# navigation shape. Add a shape = add a crawler + an entry here.
_STATUTE_CRAWLERS = {
    "ny_article": crawl_public_law,
    "tx_hierarchical": crawl_public_law_tx,
    "flat_section": crawl_public_law_flat,
}

# Bespoke crawlers for states NOT on public.law — each official legislature
# site is unique, so each has its own module. Keyed by StateConfig.official_handler.
# ("ct_bespoke" is handled separately — it delegates to fetch-public.)
_OFFICIAL_CRAWLERS = {
    "il": crawl_il,
    "oh": crawl_oh,
    "pa": crawl_pa,
    "nc": crawl_nc,
    "mi": crawl_mi,
    "va": crawl_va,
    "wa": crawl_wa,
    "az": crawl_az,
    "ma": crawl_ma,
    "in": crawl_in,
    "mo": crawl_mo,
    "md": crawl_md,
    "wi": crawl_wi,
    "mn": crawl_mn,
    "sc": crawl_sc,
    "al": crawl_al,
    "la": crawl_la,
    "ok": crawl_ok,
    "ks": crawl_ks,
    "ky": crawl_ky,
    "ia": crawl_ia,
    "ne": crawl_ne,
    "id": crawl_id,
    "wv": crawl_wv,
    "hi": crawl_hi,
    "nm": crawl_nm,
    "nh": crawl_nh,
    "me": crawl_me,
    "mt": crawl_mt,
    "ri": crawl_ri,
    "de": crawl_de,
    "sd": crawl_sd,
    "nd": crawl_nd,
    "ak": crawl_ak,
    "vt": crawl_vt,
    "wy": crawl_wy,
}


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()
_KNOWN_COMMANDS = {"fetch-public", "fetch-state", "ingest", "prune"}
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
    practice_book: bool = typer.Option(
        True,
        "--practice-book/--no-practice-book",
        help="Include the full Connecticut Practice Book PDF (~3.7MB; ~30s to extract).",
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
        include_practice_book=practice_book,
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


@app.command("fetch-state")
def fetch_state(
    state: str = typer.Option(
        ..., help="State slug from config/states.yaml (e.g. 'ny')."
    ),
    out_dir: Optional[Path] = typer.Option(
        None,
        help="Output directory. Defaults to data/raw/public/<state-slug>.",
    ),
    force: bool = typer.Option(False, help="Overwrite files that already exist."),
    delay: float = typer.Option(
        0.5, help="Seconds to pause between requests (be polite to public.law)."
    ),
    max_sections: Optional[int] = typer.Option(
        None,
        help="Cap statute sections per code (smoke-test the crawl quickly).",
    ),
    statutes: bool = typer.Option(
        True, "--statutes/--no-statutes", help="Crawl statutes from public.law."
    ),
    forms: bool = typer.Option(
        True, "--forms/--no-forms", help="Fetch the registry's form specs."
    ),
    practice_rules: bool = typer.Option(
        True,
        "--practice-rules/--no-practice-rules",
        help="Fetch the registry's practice-rule specs.",
    ),
    cases: bool = typer.Option(
        False,
        "--cases/--no-cases",
        help="Seed bounded case law from CourtListener (needs COURTLISTENER_API_TOKEN).",
    ),
    max_cases: int = typer.Option(
        25, help="Max opinions to seed when --cases is set."
    ),
    pdf: bool = typer.Option(
        True, "--pdf/--no-pdf", help="Include PDF form/rule sources."
    ),
) -> None:
    """Build a state's public corpus into data/raw/ (statutes, forms, rules, cases).

    Statutes come from <state>.public.law; forms and practice rules from the
    registry's explicit per-state URLs; case law (optional) from CourtListener.
    """
    cfg = get_state(state)
    out = out_dir or Path("data/raw/public") / cfg.slug
    out.mkdir(parents=True, exist_ok=True)

    # Connecticut isn't on public.law — its authoritative corpus comes from
    # the official cga.ct.gov / jud.ct.gov sources via the bespoke fetcher.
    # Delegate fully (it writes its own files + manifest under `out`).
    if cfg.fetcher == "official" and cfg.official_handler == "ct_bespoke":
        console.print(
            f"[cyan]{cfg.name}[/cyan]: official sources (public.law has no {cfg.slug})."
        )
        m = fetch_public_starter(
            out_dir=out,
            force=force,
            include_statutes=statutes,
            include_practice_book=True,
            include_guides=True,
            include_forms=forms,
            include_pdfs=pdf,
            console=console,
        )
        c = m["counts"]
        console.print(
            f"[green]✓[/green] {cfg.name} corpus ready in [bold]{out}[/bold]. "
            f"fetched={c['fetched']}, skipped={c['skipped']}, failed={c['failed']}"
        )
        console.print(
            f"Next:\n"
            f"  [cyan]python -m ingest.main {out} --state {cfg.slug} --dry-run[/cyan]\n"
            f"  [cyan]python -m ingest.main {out} --state {cfg.slug}[/cyan]"
        )
        return

    records: dict[str, list[dict[str, str]]] = {
        "statutes": [], "forms": [], "practice_rules": [], "cases": []
    }

    if statutes and cfg.fetcher == "official":
        crawler = _OFFICIAL_CRAWLERS.get(cfg.official_handler or "")
        if crawler is None:
            raise typer.BadParameter(
                f"no official crawler registered for {cfg.slug!r} "
                f"(official_handler={cfg.official_handler!r})"
            )
        records["statutes"] = crawler(
            cfg, out_dir=out, force=force, delay=delay,
            max_sections=max_sections, console=console,
        )
    elif statutes:
        for code in cfg.statutes:
            crawler = _STATUTE_CRAWLERS[code.layout]
            records["statutes"].extend(
                crawler(
                    subdomain=cfg.public_law_subdomain,
                    code=code,
                    state_name=cfg.name,
                    out_dir=out,
                    force=force,
                    delay=delay,
                    max_sections=max_sections,
                    console=console,
                )
            )

    if forms:
        records["forms"] = fetch_specs(
            cfg.forms, out, "forms", force=force, include_pdfs=pdf, console=console
        )
    if practice_rules:
        records["practice_rules"] = fetch_specs(
            cfg.practice_rules, out, "practice_rules",
            force=force, include_pdfs=pdf, console=console,
        )

    if cases:
        from ingest.src.courtlistener import fetch_courtlistener_cases

        records["cases"] = fetch_courtlistener_cases(
            cfg, out, max_cases=max_cases, force=force, console=console
        )
    elif cfg.courtlistener_courts:
        console.print(
            "[dim]case law available via --cases "
            "(needs COURTLISTENER_API_TOKEN)[/dim]"
        )

    def _count(recs: list[dict[str, str]], status: str) -> int:
        return sum(1 for r in recs if r.get("status") == status)

    manifest = {
        "state": cfg.slug,
        "name": cfg.name,
        "counts": {
            kind: {
                "fetched": _count(recs, "fetched"),
                "skipped": _count(recs, "skipped"),
                "failed": _count(recs, "failed"),
                "total": len(recs),
            }
            for kind, recs in records.items()
        },
        "documents": records,
    }
    (out / "public_sources_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    totals = manifest["counts"]
    console.print(
        f"[green]✓[/green] {cfg.name} corpus ready in [bold]{out}[/bold]. "
        + ", ".join(f"{k}={v['fetched']}/{v['total']}" for k, v in totals.items())
    )
    console.print(
        f"Next:\n"
        f"  [cyan]python -m ingest.main {out} --state {cfg.slug} --dry-run[/cyan]\n"
        f"  [cyan]python -m ingest.main {out} --state {cfg.slug}[/cyan]"
    )


@app.command()
def ingest(
    source: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=True),
    state: Optional[str] = typer.Option(
        None,
        help="State slug (e.g. 'ny') — writes to that state's collection. "
        "Omit for Connecticut (the default collection).",
    ),
    collection: Optional[str] = typer.Option(
        None,
        help="pgvector collection name. Overrides --state. Defaults to the "
        "active profile's (Connecticut) collection.",
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

    target = collection or collection_for(state)
    console.print(f"\nEmbedding [bold]{len(chunks)}[/bold] chunks…")
    write_chunks(chunks, collection=target, connection=connection)
    console.print(
        f"[green]✓[/green] Ingested {len(chunks)} chunks from {len(files)} files "
        f"into [bold]{target}[/bold]"
    )


@app.command()
def prune(
    base: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True,
        help="Case directory whose chunks to reconcile (e.g. data/case/s3/<id>).",
    ),
    collection: Optional[str] = typer.Option(
        None,
        help="pgvector collection name. Defaults to the active profile's collection.",
    ),
    connection: Optional[str] = typer.Option(
        None,
        help="Override LAWAGENT_PG_URL for this run.",
    ),
    dry_run: bool = typer.Option(
        False, help="Show what would be deleted without writing to the DB.",
    ),
) -> None:
    """Delete pgvector chunks under `base` whose source file is gone from disk.

    Pairs with the deletion handling in s3fetch / pdf2text: those stages
    remove docs/ and text/ files; this step removes the matching chunks.
    """
    target = collection or active_collection()
    # Match how ingest writes source_path (absolute, no trailing slash on dirs).
    prefix = str(base.resolve())
    paths = list_source_paths_under(
        prefix + "/", collection=target, connection=connection,
    )
    stale = [p for p in paths if not Path(p).exists()]
    if not stale:
        console.print(
            f"[green]✓[/green] No stale chunks under [bold]{base}[/bold] "
            f"in '{target}'."
        )
        return

    if dry_run:
        console.print(
            f"Would delete chunks for {len(stale)} missing files:"
        )
        for p in stale:
            console.print(f"  - {p}")
        return

    removed = delete_chunks_by_source_paths(
        stale, collection=target, connection=connection,
    )
    console.print(
        f"[green]✓[/green] Pruned {removed} chunks from {len(stale)} missing "
        f"files under [bold]{base}[/bold]."
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] not in _KNOWN_COMMANDS | _ROOT_FLAGS:
        sys.argv.insert(1, "ingest")
    app()
