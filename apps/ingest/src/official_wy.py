"""Wyoming divorce statutes — Wyo. Stat. Title 20, Chapter 2 (Divorce and
Alimony), from wyoleg.gov.

wyoleg.gov is an Angular SPA with no public statute API, but it serves each
title as a static PDF. We extract title20.pdf, slice out Chapter 2, and split
on the `20-2-N.` section headings.
"""
from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_pdf_text, write_statute_section

_TITLE_PDF = "https://www.wyoleg.gov/statutes/compress/title20.pdf"
_CITATION = "Wyo. Stat. § {section}"
_ISSUING = "Wyoming Legislature"
_HEADING = re.compile(r"(?m)^\s*(20-2-\d+)\.\s+(.+)")


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
    console.print("crawling [cyan]Wyo. Stat. Title 20, Ch. 2[/cyan] @ wyoleg.gov (PDF)")
    text = fetch_pdf_text(_TITLE_PDF, browser_ua=True, timeout=120)

    # Restrict to Chapter 2 (Dissolution of Marriage).
    start = text.find("CHAPTER 2 - DISSOLUTION OF MARRIAGE")
    nxt = text.find("CHAPTER 3", start + 1) if start >= 0 else -1
    chapter = text[start:nxt if nxt > 0 else None] if start >= 0 else text

    matches = list(_HEADING.finditer(chapter))
    best: dict[str, tuple[str, str]] = {}
    for i, m in enumerate(matches):
        num = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(chapter)
        block = chapter[m.start():end].strip()
        if re.search(r"repealed|renumbered", m.group(2), re.I):
            continue
        title = m.group(2).split(".", 1)[0].strip()
        if num not in best or len(block) > len(best[num][1]):
            best[num] = (title, block)

    records: list[dict[str, str]] = []
    for num in sorted(best, key=lambda n: int(n.rsplit("-", 1)[-1])):
        title, block = best[num]
        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"wy-stat-{_slugify(num)}",
                citation=_CITATION.format(section=num),
                title=title,
                section=num,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=_TITLE_PDF,
                body=block,
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
