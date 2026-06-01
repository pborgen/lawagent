"""Washington divorce statutes — RCW Chapter 26.09 (Dissolution Proceedings—
Legal Separation), from the official app.leg.wa.gov.

Static (server-rendered ASP.NET). The chapter TOC links to each section
(de-dupe the HTML vs PDF pair); the statute text is the first non-empty
direct-child `<div>` of `#contentWrapper` (the trailing session-law history
`[ ... ]` and "Notes:" blocks are separate sibling divs, so excluded).
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_CHAPTER_TOC = "https://app.leg.wa.gov/rcw/default.aspx?cite=26.09"
_SECTION_URL = "https://app.leg.wa.gov/rcw/default.aspx?cite={num}"
_CITATION = "Wash. Rev. Code § {section}"
_ISSUING = "Washington State Legislature"
_CITE = re.compile(r"cite=(26\.09\.\d+)")


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
    console.print("crawling [cyan]Wash. Rev. Code 26.09[/cyan] @ app.leg.wa.gov")
    toc = BeautifulSoup(fetch_html(_CHAPTER_TOC), "html.parser")

    nums: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        if "pdf=true" in a["href"].lower():
            continue
        m = _CITE.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"wa-rcw-{_slugify(num)}"
        url = _SECTION_URL.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                wrap = ssoup.select_one("#contentWrapper")
                body = ""
                if wrap:
                    divs = [
                        d for d in wrap.find_all("div", recursive=False)
                        if d.get_text(strip=True)
                    ]
                    if divs:
                        body = divs[0].get_text("\n", strip=True)
                h2 = ssoup.find("h2")
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num),
                        title=h2.get_text(" ", strip=True) if h2 else "",
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
