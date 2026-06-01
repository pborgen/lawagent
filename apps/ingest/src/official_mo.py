"""Missouri divorce statutes — RSMo Chapter 452 (Dissolution of Marriage,
Divorce, Alimony and Separate Maintenance), from the official revisor.mo.gov.

Static (server-rendered ASP.NET). The chapter TOC anchors carry the section
number in a `section=452.x` query param; each section page holds its text in
`div.norm`, with the catchline in `span.bold`.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_CHAPTER_TOC = "https://revisor.mo.gov/main/OneChapter.aspx?chapter=452"
_SECTION_URL = "https://revisor.mo.gov/main/OneSection.aspx?section={num}"
_CITATION = "Mo. Rev. Stat. § {section}"
_ISSUING = "Missouri General Assembly"
_SEC = re.compile(r"section=(452\.\d+)")


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
    console.print("crawling [cyan]Mo. Rev. Stat. Chapter 452[/cyan] @ revisor.mo.gov")
    toc = BeautifulSoup(fetch_html(_CHAPTER_TOC), "html.parser")

    nums: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        m = _SEC.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"mo-rsmo-{_slugify(num)}"
        url = _SECTION_URL.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                norm = ssoup.select_one("div.norm")
                body = norm.get_text("\n", strip=True).replace("\xa0", " ") if norm else ""
                title = ""
                bold = ssoup.select_one("div.norm span.bold")
                if bold:
                    t = bold.get_text(" ", strip=True).replace("\xa0", " ")
                    title = re.sub(rf"^{re.escape(num)}\.\s*", "", t).strip().rstrip("—").strip()
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
