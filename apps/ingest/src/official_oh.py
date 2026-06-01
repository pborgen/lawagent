"""Ohio divorce statutes — Ohio Revised Code Chapter 3105 (Divorce, Alimony,
Annulment, Dissolution of Marriage), from the official codes.ohio.gov.

Static HTML: the chapter page lists every section in a `table.laws-table`;
each section page holds its text in `section.laws-body` with the heading in
the `<h1>` (as "Section N | Title").
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

_CHAPTER_URL = "https://codes.ohio.gov/ohio-revised-code/chapter-3105"
_CITATION = "Ohio Rev. Code § {section}"
_ISSUING = "Ohio General Assembly"
_HREF = re.compile(r"section-(3105\.\d+)")


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
    console.print("crawling [cyan]Ohio R.C. Chapter 3105[/cyan] @ codes.ohio.gov")
    soup = BeautifulSoup(fetch_html(_CHAPTER_URL), "html.parser")

    sections: list[tuple[str, str]] = []  # (number, url)
    seen: set[str] = set()
    for a in soup.select("table.laws-table a[href*='section-3105']"):
        m = _HREF.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            # hrefs are relative ("section-3105.01"); join against the chapter
            # URL so the /ohio-revised-code/ path segment is preserved.
            sections.append((m.group(1), urljoin(_CHAPTER_URL, a["href"])))

    records: list[dict[str, str]] = []
    for num, url in sections:
        slug = f"oh-rc-{_slugify(num)}"
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                body_el = ssoup.select_one("section.laws-body")
                h1 = ssoup.find("h1")
                title = ""
                if h1 and "|" in h1.get_text():
                    title = h1.get_text().split("|", 1)[1]
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir,
                        slug=slug,
                        citation=_CITATION.format(section=num),
                        title=title,
                        section=num,
                        jurisdiction=cfg.name,
                        issuing_body=_ISSUING,
                        source_url=url,
                        body=body_el.get_text("\n", strip=True) if body_el else "",
                        force=force,
                        console=console,
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
