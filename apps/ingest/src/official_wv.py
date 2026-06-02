"""West Virginia divorce statutes — W. Va. Code Chapter 48 (Domestic Relations),
divorce-relevant articles 48-4/5/5A/6/7/8, from code.wvlegislature.gov.

Static HTML, two-level crawl: chapter TOC -> article pages -> section pages.
Body is `#results-box .sec-head`; the authoritative section number is in the
page `<title>` ("West Virginia Code | §48-8-103").
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_BASE = "https://code.wvlegislature.gov"
_CHAPTER_TOC = "https://code.wvlegislature.gov/48/"
_CITATION = "W. Va. Code § {section}"
_ISSUING = "West Virginia Legislature"
# Divorce corpus: 48-4 Annulment, 48-5 Divorce, 48-5A, 48-6, 48-7 Equitable
# Distribution, 48-8 Spousal Support.
_ARTICLES = {"48-4", "48-5", "48-5A", "48-6", "48-7", "48-8"}
_ART_HREF = re.compile(r"^/(48-\d+[A-Z]?)/$")


def _section_href(article: str) -> re.Pattern:
    return re.compile(rf"^/{re.escape(article)}-\d+[A-Z]?/?$")


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
    console.print("crawling [cyan]W. Va. Code Chapter 48 (divorce)[/cyan] @ code.wvlegislature.gov")

    toc = BeautifulSoup(fetch_html(_CHAPTER_TOC), "html.parser")
    box = toc.select_one("#results-box") or toc
    articles = []
    for a in box.find_all("a", href=True):
        m = _ART_HREF.match(a["href"])
        if m and m.group(1) in _ARTICLES and m.group(1) not in articles:
            articles.append(m.group(1))

    section_urls: list[str] = []
    seen: set[str] = set()
    for article in articles:
        time.sleep(delay)
        apage = BeautifulSoup(fetch_html(urljoin(_BASE, f"/{article}/")), "html.parser")
        abox = apage.select_one("#results-box") or apage
        href_re = _section_href(article)
        for a in abox.find_all("a", href=True):
            if href_re.match(a["href"]):
                url = urljoin(_BASE, a["href"])
                if url not in seen:
                    seen.add(url)
                    section_urls.append(url)

    records: list[dict[str, str]] = []
    for url in section_urls:
        time.sleep(delay)
        try:
            ssoup = BeautifulSoup(fetch_html(url), "html.parser")
            title_tag = ssoup.title.get_text(" ", strip=True) if ssoup.title else ""
            num = title_tag.split("§")[-1].strip() if "§" in title_tag else url.strip("/").rsplit("/", 1)[-1]
            slug = f"wv-code-{_slugify(num)}"
            if (statutes_dir / f"{slug}.txt").exists() and not force:
                console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
                records.append({"slug": slug, "url": url, "status": "skipped"})
                continue
            head = ssoup.select_one("#results-box .sec-head")
            body = re.sub(r"\s+", " ", head.get_text(" ", strip=True)) if head else ""
            tm = re.search(rf"§\s*{re.escape(num)}\.\s*(.+?)(?:\s*\([a-z]\)|$)", body)
            records.append(
                write_statute_section(
                    statutes_dir=statutes_dir, slug=slug,
                    citation=_CITATION.format(section=num),
                    title=tm.group(1).strip() if tm else "",
                    section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                    source_url=url, body=body, force=force, console=console,
                )
            )
        except Exception as exc:
            console.print(f"  [red]failed[/red] {url}: {exc}")
            records.append({"slug": url, "url": url, "status": "failed", "error": str(exc)})
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
