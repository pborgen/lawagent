"""Maine divorce statutes — Me. Rev. Stat. Title 19-A, Chapter 29 (Divorce),
from legislature.maine.gov.

Static HTML. The chapter TOC links each section as title19-Asec{N}.html; the
body is `div.MRSSection`, heading from the page `<title>`.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_BASE = "https://legislature.maine.gov/statutes/19-A/"
_TOC_URL = "https://legislature.maine.gov/statutes/19-A/title19-Ach29sec0.html"
_SECTION_URL = "https://legislature.maine.gov/statutes/19-A/title19-Asec{num}.html"
_CITATION = "Me. Stat. tit. 19-A, § {section}"
_ISSUING = "Maine Legislature"
_HREF = re.compile(r"title19-Asec([0-9A-Za-z\-]+)\.html")
_TITLE = re.compile(r"§\s*[0-9A-Za-z\-]+\s*:\s*(.+)$")


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
    console.print("crawling [cyan]Me. Rev. Stat. Title 19-A, Ch. 29[/cyan] @ legislature.maine.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    nums: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        m = _HREF.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"me-stat-19a-{_slugify(num)}"
        url = _SECTION_URL.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                sec = ssoup.select_one("div.MRSSection") or ssoup.select_one("div.section-content")
                title = ""
                if ssoup.title:
                    tm = _TITLE.search(ssoup.title.get_text(" ", strip=True).replace("\xa0", " "))
                    title = tm.group(1).strip() if tm else ""
                body = sec.get_text("\n", strip=True).replace("\xa0", " ") if sec else ""
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num), title=title,
                        section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                        source_url=url, body=body, force=force, console=console,
                    )
                )
            except Exception as exc:
                console.print(f"  [red]failed[/red] {slug}: {exc}")
                records.append({"slug": slug, "url": url, "status": "failed",
                                "error": str(exc)})
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
