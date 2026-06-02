"""Delaware divorce statutes — Del. Code Title 13, Chapter 15 (Divorce and
Annulment), from delcode.delaware.gov.

Static HTML. The whole chapter is one page; each section is a `div.Section`
whose `div.SectionHead` carries `id="<number>"` and the heading.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_CHAPTER_URL = "https://delcode.delaware.gov/title13/c015/index.html"
_CITATION = "Del. Code tit. 13, § {section}"
_ISSUING = "Delaware General Assembly"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ").replace(" ", " ")).strip()


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
    console.print("crawling [cyan]Del. Code Title 13, Ch. 15[/cyan] @ delcode.delaware.gov")
    soup = BeautifulSoup(fetch_html(_CHAPTER_URL), "html.parser")

    records: list[dict[str, str]] = []
    for sec in soup.select("div.Section"):
        head = sec.find("div", class_="SectionHead")
        if head is None or not head.get("id"):
            continue
        num = head["id"]
        heading = _norm(head.get_text(" ", strip=True))
        heading = re.sub(rf"^§\s*{re.escape(num)}\.\s*", "", heading).strip().rstrip(".")
        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"de-code-13-{_slugify(num)}",
                citation=_CITATION.format(section=num),
                title=heading,
                section=num,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=f"{_CHAPTER_URL}#{num}",
                body=_norm(sec.get_text(" ", strip=True)),
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
