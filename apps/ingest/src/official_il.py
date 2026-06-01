"""Illinois divorce statutes — 750 ILCS 5 (Illinois Marriage and Dissolution
of Marriage Act), from the official ilga.gov.

Illinois serves the whole Act as one static FullText HTML page; sections are
delimited by "(750 ILCS 5/N)" markers inside `div#billtextanchor`. A single
request yields every section, so there are no per-section fetches (the
`source_url` still points at each section's own static .htm for traceability).
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_FULLTEXT_URL = (
    "https://www.ilga.gov/legislation/ILCS/details?"
    "ActID=2086&ChapterID=59&SeqStart=&&ChapAct=FullText"
)
# Per-section static file, used as the citation's source_url.
_SECTION_URL = "https://www.ilga.gov/Documents/legislation/ilcs/documents/075000050K{n}.htm"
_CITATION = "750 ILCS 5/{section}"
_ISSUING = "Illinois General Assembly"

_MARKER = re.compile(r"\(750 ILCS 5/([0-9A-Za-z.\-]+)\)")
# The heading after the marker is "Sec. N. <Title>.)" — capture up to the
# first "." or ")" so we get just the title, not the body that follows.
_TITLE = re.compile(r"Sec\.\s*[0-9A-Za-z.\-]+\.\s*\n?\s*([^.)\n]+)")


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
    console.print("crawling [cyan]750 ILCS 5[/cyan] @ ilga.gov (single FullText page)")
    soup = BeautifulSoup(fetch_html(_FULLTEXT_URL), "html.parser")
    anchor = soup.find(id="billtextanchor")
    text = (anchor or soup).get_text("\n")

    matches = list(_MARKER.finditer(text))
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, m in enumerate(matches):
        section = m.group(1)
        if section in seen:
            continue
        seen.add(section)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end].strip()
        title_m = _TITLE.search(body)
        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"il-750-ilcs-5-{_slugify(section)}",
                citation=_CITATION.format(section=section),
                title=title_m.group(1) if title_m else "",
                section=section,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=_SECTION_URL.format(n=section),
                body=body,
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
