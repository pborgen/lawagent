"""Nebraska divorce statutes — Neb. Rev. Stat. Chapter 42 (Households and
Families), dissolution range §§ 42-347 to 42-381, from nebraskalegislature.gov.

Static HTML. The chapter browse page links each section; the body is
`div.statute p.text-justify` (excludes the Source/Annotations blocks), number
in `div.statute h2`, heading in `div.statute h3`.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_TOC_URL = "https://nebraskalegislature.gov/laws/browse-chapters.php?chapter=42"
_SECTION_URL = "https://nebraskalegislature.gov/laws/statutes.php?statute={num}"
_CITATION = "Neb. Rev. Stat. § {section}"
_ISSUING = "Nebraska Legislature"
_STAT = re.compile(r"statute=(42-[\w.]+)")
_LEAD = re.compile(r"^(\d+)")


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
    console.print("crawling [cyan]Neb. Rev. Stat. Chapter 42 (dissolution)[/cyan] @ nebraskalegislature.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    nums: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        m = _STAT.search(a["href"])
        if not m or m.group(1) in seen:
            continue
        sub = m.group(1).split("-", 1)[1]  # e.g. "365" or "349.01"
        lead = _LEAD.match(sub)
        if not lead or not (347 <= int(lead.group(1)) <= 381):
            continue
        seen.add(m.group(1))
        nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"ne-stat-{_slugify(num)}"
        url = _SECTION_URL.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                box = BeautifulSoup(fetch_html(url), "html.parser").select_one("div.statute")
                title = ""
                body = ""
                if box:
                    h3 = box.find("h3")
                    title = h3.get_text(" ", strip=True) if h3 else ""
                    body = "\n\n".join(
                        p.get_text(" ", strip=True) for p in box.select("p.text-justify")
                        if p.get_text(strip=True)
                    )
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num), title=title,
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
