"""Indiana divorce statutes — Ind. Code Title 31, Article 15 (Dissolution of
Marriage and Legal Separation), from the official iga.in.gov.

The browse UI (/laws/...) is a React SPA, but iga.in.gov also serves each
title as a static HTML file. We fetch Title 31 once; each section is a
`<div class="section" id="31-15-X-Y">` holding the heading spans, and the
statute text is the run of `<p>` siblings until the next section div.
"""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html_browser, write_statute_section

_YEAR = "2025"
_TITLE_HTML = f"https://iga.in.gov/ic/{_YEAR}/Title_31.html"
_SECTION_URL = f"https://iga.in.gov/ic/{_YEAR}/Title_31.html#{{section}}"
_CITATION = "Ind. Code § {section}"
_ISSUING = "Indiana General Assembly"
_ARTICLE = "31-15-"  # Dissolution of Marriage and Legal Separation


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
    console.print("crawling [cyan]Ind. Code Title 31, Art. 15[/cyan] @ iga.in.gov")
    # iga.in.gov serves a JS shell to non-browser UAs and the 5.7MB title file
    # needs a longer timeout, so use the browser-UA fetch.
    soup = BeautifulSoup(fetch_html_browser(_TITLE_HTML), "html.parser")

    section_divs = [
        d for d in soup.find_all("div", class_="section")
        if (d.get("id") or "").startswith(_ARTICLE)
    ]

    records: list[dict[str, str]] = []
    for d in section_divs:
        num = d["id"]
        desc = d.find(id="shortdescription")
        title = desc.get_text(" ", strip=True) if desc else ""
        # Body = the <p> siblings after this section div, up to the next section.
        parts: list[str] = []
        sib = d.find_next_sibling()
        while sib is not None:
            classes = sib.get("class") or [] if hasattr(sib, "get") else []
            if sib.name == "div" and "section" in classes and sib.get("id"):
                break
            text = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else ""
            if text:
                parts.append(text)
            sib = sib.find_next_sibling()

        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"in-ic-{_slugify(num)}",
                citation=_CITATION.format(section=num),
                title=title,
                section=num,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=_SECTION_URL.format(section=num),
                body="\n\n".join(parts),
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
