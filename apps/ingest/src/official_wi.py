"""Wisconsin divorce statutes — Wis. Stat. Chapter 767 (Actions Affecting the
Family), from the official docs.legis.wisconsin.gov.

Static HTML. The chapter TOC links each section via /document/statutes/{num}
(a redirect alias). Section pages are per-subchapter and bundle several
sections, so we pick the target by its `span.qsnum_sect` and collect the
section's `div.qsatxt_*` blocks up to the next `div.qsatxt_1sect`.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_TOC_URL = "https://docs.legis.wisconsin.gov/statutes/statutes/767"
_SECTION_URL = "https://docs.legis.wisconsin.gov/document/statutes/{num}"
_CITATION = "Wis. Stat. § {section}"
_ISSUING = "Wisconsin Legislature"
# Require a digit after the dot so the chapter PDF link (767.pdf) isn't matched.
_HREF = re.compile(r"/document/statutes/(767\.\d\w*)")


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
    console.print("crawling [cyan]Wis. Stat. Chapter 767[/cyan] @ docs.legis.wisconsin.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    nums: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        m = _HREF.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"wi-stat-{_slugify(num)}"
        url = _SECTION_URL.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                target = None
                for d in ssoup.select("div.qsatxt_1sect"):
                    numspan = d.select_one("span.qsnum_sect")
                    if numspan and numspan.get_text(strip=True) == num:
                        target = d
                        break
                title = ""
                body = ""
                if target is not None:
                    ts = target.select_one("span.qstitle_sect")
                    title = ts.get_text(" ", strip=True) if ts else ""
                    parts = [target.get_text(" ", strip=True)]
                    sib = target.find_next_sibling()
                    while sib is not None:
                        classes = sib.get("class") or [] if hasattr(sib, "get") else []
                        if "qsatxt_1sect" in classes:
                            break
                        if getattr(sib, "name", None) == "div" and any(
                            c.startswith("qsatxt") for c in classes
                        ):
                            t = sib.get_text(" ", strip=True)
                            if t:
                                parts.append(t)
                        sib = sib.find_next_sibling()
                    body = "\n\n".join(parts)
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
