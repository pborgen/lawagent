"""Minnesota divorce statutes — Minn. Stat. Chapter 518 (Marriage Dissolution),
from the official revisor.mn.gov.

Static HTML. The chapter TOC links each section as /statutes/cite/518.x; each
section page holds its text in `div.section` with the headnote in `h1.shn`.
Repealed/renumbered rows are skipped.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_TOC_URL = "https://www.revisor.mn.gov/statutes/cite/518"
_SECTION_URL = "https://www.revisor.mn.gov/statutes/cite/{num}"
_CITATION = "Minn. Stat. § {section}"
_ISSUING = "Minnesota Legislature"
_HREF = re.compile(r"^/statutes/cite/(518\.\w+)$")
_HEAD = re.compile(r"^(\d+\.\w+)\s+(.*)$", re.S)


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
    console.print("crawling [cyan]Minn. Stat. Chapter 518[/cyan] @ revisor.mn.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    nums: list[str] = []
    seen: set[str] = set()
    for a in toc.select('a[href^="/statutes/cite/518."]'):
        m = _HREF.match(a["href"])
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        row = a.find_parent("tr")
        rowtext = (row.get_text(" ", strip=True) if row else "").lower()
        if "[repealed" in rowtext or "renumbered, repealed" in rowtext:
            continue
        nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"mn-stat-{_slugify(num)}"
        url = _SECTION_URL.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                sec = ssoup.select_one("div.section")
                h1 = ssoup.select_one("h1.shn")
                title = ""
                if h1:
                    hm = _HEAD.match(h1.get_text(" ", strip=True))
                    title = hm.group(2) if hm else h1.get_text(" ", strip=True)
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num), title=title,
                        section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                        source_url=url,
                        body=sec.get_text("\n", strip=True) if sec else "",
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
