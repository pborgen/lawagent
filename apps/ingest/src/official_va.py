"""Virginia divorce statutes — Code of Virginia Title 20, Chapter 6 (Divorce,
Affirmation and Annulment), from the official law.lis.virginia.gov.

Static HTML. The chapter TOC links to per-section pages; each holds its text
in `section.body.editable` with the heading in an `<h2>` that contains "§".
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_BASE = "https://law.lis.virginia.gov"
_CHAPTER_TOC = "https://law.lis.virginia.gov/vacode/title20/chapter6/"
_CITATION = "Va. Code § {section}"
_ISSUING = "Virginia General Assembly"
_SEC_HREF = re.compile(r"/vacode/title20/chapter[\w.]+/section([\w.:\-]+?)/?$")
_TITLE = re.compile(r"§\s*[\w.:\-]+\s*\.?\s*(.*)")


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
    console.print("crawling [cyan]Va. Code Title 20, Ch. 6[/cyan] @ law.lis.virginia.gov")
    toc = BeautifulSoup(fetch_html(_CHAPTER_TOC), "html.parser")

    sections: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in toc.select("a[href*='/section']"):
        m = _SEC_HREF.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            sections.append((m.group(1), urljoin(_BASE, a["href"])))

    records: list[dict[str, str]] = []
    for num, url in sections:
        slug = f"va-code-{_slugify(num)}"
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                body_el = ssoup.select_one("section.body.editable")
                title = ""
                for h2 in ssoup.find_all("h2"):
                    t = h2.get_text(" ", strip=True)
                    if "§" in t:
                        tm = _TITLE.match(t)
                        title = tm.group(1) if tm else t
                        break
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num), title=title,
                        section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                        source_url=url,
                        body=body_el.get_text("\n", strip=True) if body_el else "",
                        force=force, console=console,
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
