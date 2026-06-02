"""Montana divorce statutes — Mont. Code Ann. Title 40, Chapter 4 (Termination
of Marriage...), from mca.legmt.gov.

Static HTML, three-level crawl: parts index -> per-part sections index ->
section pages. Body is `div.section-content`, number in `span.citation`,
heading in `h1.section-section-title`. (Section file names use a within-part
sequence, not the printed number, so we must crawl the indexes.)
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_PARTS_INDEX = "https://mca.legmt.gov/bills/mca/title_0400/chapter_0040/parts_index.html"
_CITATION = "Mont. Code § {section}"
_ISSUING = "Montana Legislature"


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
    console.print("crawling [cyan]Mont. Code Title 40, Ch. 4[/cyan] @ mca.legmt.gov")

    parts = BeautifulSoup(fetch_html(_PARTS_INDEX), "html.parser")
    part_urls = [
        urljoin(_PARTS_INDEX, a["href"])
        for a in parts.find_all("a", href=True)
        if a["href"].endswith("sections_index.html")
    ]

    section_urls: list[str] = []
    seen: set[str] = set()
    for purl in dict.fromkeys(part_urls):
        time.sleep(delay)
        sidx = BeautifulSoup(fetch_html(purl), "html.parser")
        for a in sidx.find_all("a", href=True):
            if "/section_" in a["href"] and a["href"].endswith(".html"):
                url = urljoin(purl, a["href"])
                if url not in seen:
                    seen.add(url)
                    section_urls.append(url)

    records: list[dict[str, str]] = []
    for url in section_urls:
        time.sleep(delay)
        try:
            ssoup = BeautifulSoup(fetch_html(url), "html.parser")
            cite = ssoup.select_one("span.citation")
            num = cite.get_text(strip=True) if cite else ""
            if not num:
                continue
            slug = f"mt-code-{_slugify(num)}"
            if (statutes_dir / f"{slug}.txt").exists() and not force:
                console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
                records.append({"slug": slug, "url": url, "status": "skipped"})
                continue
            h1 = ssoup.select_one("h1.section-section-title")
            content = ssoup.select_one("div.section-content")
            records.append(
                write_statute_section(
                    statutes_dir=statutes_dir, slug=slug,
                    citation=_CITATION.format(section=num),
                    title=h1.get_text(" ", strip=True) if h1 else "",
                    section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                    source_url=url,
                    body=content.get_text("\n", strip=True) if content else "",
                    force=force, console=console,
                )
            )
        except Exception as exc:
            console.print(f"  [red]failed[/red] {url}: {exc}")
            records.append({"slug": url, "url": url, "status": "failed", "error": str(exc)})
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
