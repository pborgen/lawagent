"""Kansas divorce statutes — Kan. Stat. Chapter 23 (Family Law Code),
Articles 27 (Divorce), 28 (Property), 29 (Maintenance), from the official
Kansas Revisor of Statutes (ksrevisor.gov).

Static HTML. The chapter TOC links each section; the operative text is in
`.ksa_stat` (excludes history/annotation blocks), number in `.stat_number`,
caption in `.stat_caption`.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_BASE = "https://www.ksrevisor.gov/statutes/"
_TOC_URL = "https://www.ksrevisor.gov/statutes/ksa_ch23.html"
_CITATION = "Kan. Stat. § {section}"
_ISSUING = "Kansas Legislature"
# Divorce corpus = Article 27 (Divorce), 28 (Property), 29 (Maintenance).
_ARTICLES = ("/023_027_", "/023_028_", "/023_029_")


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
    console.print("crawling [cyan]Kan. Stat. Chapter 23 (Arts. 27-29)[/cyan] @ ksrevisor.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    urls: list[str] = []
    seen: set[str] = set()
    for a in toc.select('a[href*="/ch23/"]'):
        href = a["href"]
        if any(art in href for art in _ARTICLES) and href not in seen:
            seen.add(href)
            urls.append(urljoin(_BASE, href))

    records: list[dict[str, str]] = []
    for url in urls:
        time.sleep(delay)
        try:
            ssoup = BeautifulSoup(fetch_html(url), "html.parser")
            numel = ssoup.select_one(".stat_number")
            num = numel.get_text(strip=True).rstrip(".") if numel else ""
            if not num:
                continue
            slug = f"ks-stat-{_slugify(num)}"
            if (statutes_dir / f"{slug}.txt").exists() and not force:
                console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
                records.append({"slug": slug, "url": url, "status": "skipped"})
            else:
                cap = ssoup.select_one(".stat_caption")
                body = " ".join(
                    s.get_text(" ", strip=True) for s in ssoup.select(".ksa_stat")
                ).strip()
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num),
                        title=cap.get_text(" ", strip=True) if cap else "",
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
