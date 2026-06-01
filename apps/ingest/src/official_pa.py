"""Pennsylvania divorce statutes — 23 Pa.C.S. Part IV (Divorce), from the
official legis.state.pa.us.

Pennsylvania serves all of Title 23 (Domestic Relations) as one static legacy
HTML file with no per-section markup — sections are plain `<p>` paragraphs
whose heading reads "§ NNNN. Title.". We parse those headings, group the
paragraphs between them, and keep only the Divorce chapters (31/33/35/37/39,
i.e. section numbers 3100-3999). Each number appears twice (table of contents
then body); we keep the longer block (the body).
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, write_statute_section
from ingest.src.fetch_public import _download

_TITLE23_URL = "https://www.legis.state.pa.us/WU01/LI/LI/CT/HTM/23/23.HTM"
_CITATION = "23 Pa.C.S. § {section}"
_ISSUING = "Pennsylvania General Assembly"
# A paragraph that begins a section: "§ 3301. Grounds for divorce."
_HEADING = re.compile(r"^§\s*(\d+(?:\.\d+)?)\.\s+(.*)$")
_TITLE = re.compile(r"^§\s*\d+(?:\.\d+)?\.\s+([^.]+)")
# Part IV Divorce = chapters 31, 33, 35, 37, 39 -> 3100-3999, odd hundreds.
_DIVORCE = re.compile(r"^3[13579]\d\d$")


def _paragraphs() -> list[str]:
    # This file is latin-1/IE-era HTML; decode leniently and normalize nbsp.
    html = _download(_TITLE23_URL).decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for p in soup.find_all("p"):
        text = re.sub(r"\s+", " ", p.get_text(" ", strip=True).replace("\xa0", " ")).strip()
        if text:
            out.append(text)
    return out


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
    console.print("crawling [cyan]23 Pa.C.S. (Divorce)[/cyan] @ legis.state.pa.us")
    paras = _paragraphs()

    headings: list[tuple[int, str]] = []  # (paragraph index, section number)
    for idx, text in enumerate(paras):
        m = _HEADING.match(text)
        if m and _DIVORCE.match(m.group(1)):
            headings.append((idx, m.group(1)))

    # Build each section's block; for a number seen twice (TOC + body) keep the
    # longer block.
    best: dict[str, str] = {}
    for hi, (idx, num) in enumerate(headings):
        end = headings[hi + 1][0] if hi + 1 < len(headings) else len(paras)
        block = "\n\n".join(paras[idx:end]).strip()
        if num not in best or len(block) > len(best[num]):
            best[num] = block

    records: list[dict[str, str]] = []
    for num in sorted(best):
        block = best[num]
        title_m = _TITLE.match(block)
        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"pa-23-pacs-{_slugify(num)}",
                citation=_CITATION.format(section=num),
                title=title_m.group(1) if title_m else "",
                section=num,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=_TITLE23_URL,
                body=block,
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
