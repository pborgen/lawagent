"""Kentucky divorce statutes — KRS Chapter 403 (Dissolution of Marriage),
from the official Kentucky Legislature (apps.legislature.ky.gov).

The chapter TOC is static HTML, but each section body is served as a PDF
(statute.aspx?id=<opaque>). We map sections -> opaque ids from the TOC, then
extract each PDF's text. Repealed/renumbered stubs are skipped.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, fetch_pdf_text, write_statute_section

_CHAPTER_TOC = "https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=39213"
_CITATION = "Ky. Rev. Stat. § {section}"
_ISSUING = "Kentucky General Assembly"
# Anchor text like ".140  Marriage -- Court may enter decree..."
_ANCHOR = re.compile(r"^\.(\d+[A-Za-z0-9-]*)\s+(.*)$", re.S)


def crawl(
    cfg: StateConfig,
    *,
    out_dir: Path,
    force: bool,
    delay: float,
    max_sections: int | None,
    console: Console,
) -> list[dict[str, str]]:
    statutes_dir = out_dir / "statutes"
    console.print("crawling [cyan]Ky. Rev. Stat. Chapter 403[/cyan] @ apps.legislature.ky.gov")
    toc = BeautifulSoup(fetch_html(_CHAPTER_TOC), "html.parser")

    sections: list[tuple[str, str, str]] = []  # (number, title, pdf_url)
    seen: set[str] = set()
    for a in toc.select('a[href*="statute.aspx"]'):
        m = _ANCHOR.match(a.get_text(" ", strip=True))
        if not m:
            continue
        num = f"403.{m.group(1)}"
        heading = m.group(2).strip()
        if num in seen or re.search(r"repealed|renumbered", heading, re.I):
            continue
        seen.add(num)
        sections.append((num, heading, urljoin(_CHAPTER_TOC, a["href"])))

    records: list[dict[str, str]] = []
    for num, heading, url in sections:
        slug = f"ky-krs-{_slugify(num)}"
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                body = fetch_pdf_text(url)
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num), title=heading,
                        section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                        source_url=url, body=body, force=force, console=console,
                    )
                )
            except Exception as exc:
                console.print(f"  [red]failed[/red] {slug}: {exc}")
                records.append({"slug": slug, "url": url, "status": "failed",
                                "error": str(exc)})
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
