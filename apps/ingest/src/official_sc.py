"""South Carolina divorce statutes — S.C. Code Title 20, Chapter 3 (Divorce),
from the official scstatehouse.gov.

The whole chapter is one static HTML page (`t20c003.php`). Sections aren't
nested — each starts at a bold `<span>SECTION 20-3-N.</span>` inside
`div#contentsection`; the body runs through the following sibling nodes
(`<br>` → newline) until the next such span.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_CHAPTER_URL = "https://www.scstatehouse.gov/code/t20c003.php"
_CITATION = "S.C. Code § {section}"
_ISSUING = "South Carolina General Assembly"
_SEC = re.compile(r"SECTION\s+(20-3-\d+)")


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
    console.print("crawling [cyan]S.C. Code Title 20, Ch. 3[/cyan] @ scstatehouse.gov")
    soup = BeautifulSoup(fetch_html(_CHAPTER_URL), "html.parser")
    container = soup.find(id="contentsection") or soup

    starts = [s for s in container.find_all("span") if _SEC.search(s.get_text(" ", strip=True))]
    start_ids = {id(s) for s in starts}

    records: list[dict[str, str]] = []
    for span in starts:
        num = _SEC.search(span.get_text(" ", strip=True)).group(1)
        pieces: list[str] = []
        sib = span.next_sibling
        while sib is not None and id(sib) not in start_ids:
            if getattr(sib, "name", None) == "br":
                pieces.append("\n")
            else:
                text = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                if text:
                    pieces.append(text)
            sib = sib.next_sibling
        body = re.sub(r"\n{3,}", "\n\n", "".join(pieces)).strip()
        body = re.split(r"\nHISTORY:", body)[0].strip()
        title = body.split("\n", 1)[0].strip()
        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"sc-code-{_slugify(num)}",
                citation=_CITATION.format(section=num),
                title=title,
                section=num,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=_CHAPTER_URL,
                body=body,
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
