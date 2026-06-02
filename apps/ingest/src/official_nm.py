"""New Mexico divorce law — NMSA 1978 Chapter 40, Article 4 (Dissolution of
Marriage), from nmonesource.com.

The official NM Compilation Commission portal is a JS document viewer with no
per-section URLs, but it serves the whole chapter as a static PDF. We extract
the chapter PDF text and split it into Article 4 sections on the `40-4-N.`
headings (dropping the trailing ANNOTATIONS case-note blocks).
"""
from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_pdf_text, write_statute_section

# Chapter 40 ("Domestic Affairs") document — id 4375.
_CHAPTER_PDF = "https://nmonesource.com/nmos/nmsa/en/4375/1/document.do"
_CITATION = "N.M. Stat. § {section}"
_ISSUING = "New Mexico Legislature"
# Section headings like "40-4-1. Dissolution of marriage."
_HEADING = re.compile(r"(?m)^(40-4-\d+(?:\.\d+)?)\.\s+(.+?)\.")


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
    console.print("crawling [cyan]NMSA Chapter 40, Art. 4[/cyan] @ nmonesource.com (chapter PDF)")
    text = fetch_pdf_text(_CHAPTER_PDF, browser_ua=True, timeout=120)

    matches = list(_HEADING.finditer(text))
    # Build each section's block; keep the longest block per number (a TOC entry
    # and the body both match — the body is longer).
    best: dict[str, tuple[str, str]] = {}  # num -> (title, block)
    for i, m in enumerate(matches):
        num = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.start():end].strip()
        block = re.split(r"\n\s*ANNOTATIONS\b", block)[0].strip()  # drop case notes
        if num not in best or len(block) > len(best[num][1]):
            best[num] = (m.group(2).strip(), block)

    def _key(n: str) -> tuple[int, int]:  # "40-4-7.3" -> (7, 3)
        last = n.rsplit("-", 1)[-1].split(".")
        return (int(last[0]), int(last[1]) if len(last) > 1 else 0)

    records: list[dict[str, str]] = []
    for num in sorted(best, key=_key):
        title, block = best[num]
        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"nm-stat-{_slugify(num)}",
                citation=_CITATION.format(section=num),
                title=title,
                section=num,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=_CHAPTER_PDF,
                body=block,
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
