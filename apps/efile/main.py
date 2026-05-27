"""CT eServices scraper CLI.

Usage:
    python -m efile.main pull
    python -m efile.main pull --crn 5124226 --headed
    python -m efile.main login            # one-time interactive login
    python -m efile.main capture          # snapshot pages to retarget selectors

By design, this app only downloads. It does NOT push files into the
vector store — that's `python -m ingest.main data/case/efile/<crn>/docs/`
after the fact, exactly as we wanted ingestion to stay separate.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from efile.src.auth import authenticated_context
from efile.src.case import fetch_case_detail
from efile.src.download import case_dir, download_documents
from settings import get_settings


def _docket_no_from_manifest(crn: str) -> Optional[str]:
    """Read the docket_no recorded by an earlier successful pull, if any."""
    manifest = case_dir(crn) / "manifest.json"
    if not manifest.exists():
        return None
    try:
        return json.loads(manifest.read_text()).get("docket_no") or None
    except (OSError, json.JSONDecodeError):
        return None


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def login(
    headed: bool = typer.Option(
        True, help="Run with a visible browser so you can watch / intervene."
    ),
) -> None:
    """Log in once and cache the session in EFILE_STORAGE_STATE."""
    with authenticated_context(headless=not headed, force_login=True):
        console.print("[green]✓[/green] Logged in and saved storage_state.")


@app.command()
def pull(
    crn: str = typer.Option(
        None, help="Case reference number. Defaults to EFILE_CRN."
    ),
    docket_no: str = typer.Option(
        None,
        help="Docket no (e.g. HHD-FA25-5089318-S). Defaults to EFILE_DOCKET_NO "
        "or the value cached in the existing manifest.",
    ),
    headed: bool = typer.Option(
        False, help="Show the browser. Helpful when first wiring up selectors."
    ),
    force_login: bool = typer.Option(
        False, help="Ignore cached session and log in again."
    ),
) -> None:
    """Fetch the case detail page and download every document in the docket."""
    settings = get_settings()
    crn = crn or settings.efile_crn or ""
    if not crn:
        console.print("[red]No CRN provided. Set EFILE_CRN or pass --crn.[/red]")
        raise typer.Exit(code=1)

    docket_no = (
        docket_no or settings.efile_docket_no or _docket_no_from_manifest(crn)
    )
    if not docket_no:
        console.print(
            "[red]No docket no available. Pass --docket-no or set "
            "EFILE_DOCKET_NO (e.g. HHD-FA25-5089318-S). It's used to prime the "
            "LoadDocket.aspx session before fetching case detail.[/red]"
        )
        raise typer.Exit(code=1)

    out_dir = case_dir(crn)
    console.print(f"Pulling case [bold]{crn}[/bold] ({docket_no}) → {out_dir}")

    with authenticated_context(
        headless=not headed, force_login=force_login
    ) as (_, context, page):
        detail = fetch_case_detail(page, crn, docket_no=docket_no)
        console.print(
            f"  Case loaded: {len(detail.docket_entries)} docket entries, "
            f"{sum(len(e.documents) for e in detail.docket_entries)} document links"
        )
        manifest = download_documents(context, detail)

    counts = manifest.get("counts", {})
    console.print(
        f"[green]✓[/green] Done. "
        f"new={counts.get('new_downloads', 0)}, "
        f"skipped={counts.get('skipped_already_present', 0)}, "
        f"entries={counts.get('total_docket_entries', 0)}"
    )
    console.print(f"Manifest: {out_dir / 'manifest.json'}")
    console.print(
        f"To ingest the new PDFs into pgvector, run:\n"
        f"  [cyan]python -m ingest.main {out_dir / 'docs'}[/cyan]"
    )


@app.command()
def probe() -> None:
    """Headless: log in, dump the eServices home + a few candidate SRP pages.

    LoadDocket.aspx is 404 now; this hits the post-login landing page and
    a handful of likely SRP-flow URLs so we can see what links the sidebar
    actually exposes and what each endpoint returns.
    """
    candidates = [
        "https://efile.eservices.jud.ct.gov/",
        "https://efile.eservices.jud.ct.gov/CaseDetail/AttyCaseHistory.aspx",
        "https://efile.eservices.jud.ct.gov/CaseLookup/CaseLookupByDocket.aspx",
        "https://efile.eservices.jud.ct.gov/CaseLookup/CaseLookupByName.aspx",
        "https://efile.eservices.jud.ct.gov/CaseDetail/MyCases.aspx",
        "https://efile.eservices.jud.ct.gov/CaseDetail/ListMyCases.aspx",
    ]
    out = Path("data/debug") / datetime.now().strftime("%Y%m%d-%H%M%S_probe")
    out.mkdir(parents=True, exist_ok=True)
    with authenticated_context(headless=True) as (_, _ctx, page):
        for i, url in enumerate(candidates, start=1):
            try:
                page.goto(url, wait_until="networkidle")
            except Exception as exc:
                (out / f"{i:02d}_error.txt").write_text(
                    f"{url}\n{exc!r}", encoding="utf-8"
                )
                continue
            label = f"{i:02d}_{url.rsplit('/', 1)[-1] or 'home'}"
            (out / f"{label}.url.txt").write_text(page.url, encoding="utf-8")
            (out / f"{label}.html").write_text(page.content(), encoding="utf-8")
            console.print(f"  [green]✓[/green] {url} → {page.url}")
    console.print(f"[green]✓[/green] Snapshots under {out}")


@app.command()
def capture() -> None:
    """Open a logged-in browser to capture page snapshots for retargeting.

    The scraper's case navigation targets the attorney eServices flow
    (AttyCaseHistory / AttyCaseDetail). Self-represented-party accounts get
    different pages, so case.py's selectors/URLs must be rewritten against the
    real SRP pages.

    This reuses the working `login` flow, then opens a visible browser already
    logged in. Navigate to a page worth capturing (your case list, the case
    docket), then return to this terminal and press Enter to snapshot it. Each
    snapshot writes the URL + full HTML under data/debug/<timestamp>/.
    """
    with authenticated_context(headless=False) as (_, _ctx, page):
        page.goto("https://efile.eservices.jud.ct.gov/", wait_until="networkidle")
        console.print(
            "[bold]Browser open and logged in.[/bold] Navigate to a page you "
            "want captured (case list, case docket)."
        )
        n = 0
        while True:
            cmd = console.input(
                "Press [bold]Enter[/bold] to snapshot the current page, "
                "or type [bold]q[/bold] then Enter to finish: "
            )
            if cmd.strip().lower() == "q":
                break
            n += 1
            out = Path("data/debug") / datetime.now().strftime("%Y%m%d-%H%M%S")
            out.mkdir(parents=True, exist_ok=True)
            (out / "url.txt").write_text(page.url, encoding="utf-8")
            (out / "page.html").write_text(page.content(), encoding="utf-8")
            console.print(f"  [green]✓[/green] snapshot {n} → {out}  ({page.url})")

    console.print(
        f"[green]✓[/green] Captured {n} page(s) under data/debug/. "
        "Share those with Claude to retarget the scraper."
    )


if __name__ == "__main__":
    app()
