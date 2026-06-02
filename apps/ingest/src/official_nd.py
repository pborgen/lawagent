"""North Dakota divorce statutes — N.D. Cent. Code Title 14, Chapter 14-05
(Divorce), from ndlegis.gov.

PDF-based: the whole chapter is one PDF. We extract its text, drop the
"Page No. N" footers, and split into sections on the `14-05-N.` headings.
"""
from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_pdf_text, write_statute_section

_CHAPTER_PDF = "https://ndlegis.gov/cencode/t14c05.pdf"
_CITATION = "N.D. Cent. Code § {section}"
_ISSUING = "North Dakota Legislative Assembly"
_HEADING = re.compile(r"(?m)^\s*(14-05-\d+(?:\.\d+)?)\.\s+(.+)")
_FOOTER = re.compile(r"(?m)^\s*Page No\.\s*\d+\s*$")


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
    console.print("crawling [cyan]N.D. Cent. Code Chapter 14-05[/cyan] @ ndlegis.gov (PDF)")
    text = _FOOTER.sub("", fetch_pdf_text(_CHAPTER_PDF))

    matches = list(_HEADING.finditer(text))
    best: dict[str, tuple[str, str]] = {}  # num -> (title, block)
    for i, m in enumerate(matches):
        num = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.start():end].strip()
        title = m.group(2).split(".", 1)[0].strip()
        if num not in best or len(block) > len(best[num][1]):
            best[num] = (title, block)

    records: list[dict[str, str]] = []
    for num in sorted(best, key=lambda n: [int(p) for p in n.replace("14-05-", "").split(".")]):
        title, block = best[num]
        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"nd-cc-{_slugify(num)}",
                citation=_CITATION.format(section=num),
                title=title,
                section=num,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=f"{_CHAPTER_PDF}#nameddest={num}",
                body=block,
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
