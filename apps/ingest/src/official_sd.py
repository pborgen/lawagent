"""South Dakota divorce statutes — S.D. Codified Laws Chapter 25-4 (Divorce and
Separate Maintenance), from sdlegislature.gov.

The browse site is a Vue SPA, but a JSON API serves the data. The chapter
object's `Html` field lists section links; each section object carries its
`CatchLine` (heading) and `Html` (body).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html_browser, write_statute_section

_CHAPTER_API = "https://sdlegislature.gov/api/Statutes/Statute/25-4"
_SECTION_API = "https://sdlegislature.gov/api/Statutes/Statute/{num}"
_SECTION_SRC = "https://sdlegislature.gov/Statutes/{num}"
_CITATION = "S.D. Codified Laws § {section}"
_ISSUING = "South Dakota Legislature"
_ANCHOR = re.compile(r"Statute=(25-4-\d+(?:\.\d+)?)")


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
    console.print("crawling [cyan]S.D. Codified Laws Chapter 25-4[/cyan] @ sdlegislature.gov (JSON API)")
    chapter = json.loads(fetch_html_browser(_CHAPTER_API))
    nums: list[str] = []
    seen: set[str] = set()
    for m in _ANCHOR.finditer(chapter.get("Html") or ""):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"sd-stat-{_slugify(num)}"
        src = _SECTION_SRC.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": src, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                d = json.loads(fetch_html_browser(_SECTION_API.format(num=num)))
                if d.get("Repealed"):
                    records.append({"slug": slug, "url": src, "status": "skipped"})
                    continue
                body = BeautifulSoup(d.get("Html") or "", "html.parser").get_text(
                    "\n", strip=True
                )
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num),
                        title=d.get("CatchLine") or "",
                        section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                        source_url=src, body=body, force=force, console=console,
                    )
                )
            except Exception as exc:
                console.print(f"  [red]failed[/red] {slug}: {exc}")
                records.append({"slug": slug, "url": src, "status": "failed",
                                "error": str(exc)})
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
