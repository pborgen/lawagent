"""Arizona divorce statutes — A.R.S. Title 25, Chapter 3 (Dissolution of
Marriage), from the official azleg.gov.

The modern viewer is JS, but the legacy per-section `.htm` files it points to
are plain static HTML. The Title 25 index links each section as
`/ars/25/NNNNN.htm` (5-digit zero-padded); Chapter 3 = the 003xx range.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_TOC_URL = "https://www.azleg.gov/arsDetail/?title=25"
_SECTION_URL = "https://www.azleg.gov/ars/25/{f}.htm"
_CITATION = "Ariz. Rev. Stat. § {section}"
_ISSUING = "Arizona State Legislature"
_HTM = re.compile(r"/ars/25/(\d{5})\.htm")


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
    console.print("crawling [cyan]Ariz. Rev. Stat. Title 25, Ch. 3[/cyan] @ azleg.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    files: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        m = _HTM.search(a["href"])
        # Chapter 3 (Dissolution of Marriage) = the 003xx file range.
        if m and m.group(1).startswith("003") and m.group(1) not in seen:
            seen.add(m.group(1))
            files.append(m.group(1))

    records: list[dict[str, str]] = []
    for f in files:
        num = f"25-{int(f)}"  # 00312 -> 312 -> "25-312"
        slug = f"az-ars-{_slugify(num)}"
        url = _SECTION_URL.format(f=f)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                title = ""
                if ssoup.title and " - " in ssoup.title.get_text():
                    title = ssoup.title.get_text().split(" - ", 1)[1]
                paras = [
                    p.get_text(" ", strip=True)
                    for p in (ssoup.body.find_all("p") if ssoup.body else [])
                    if p.get_text(strip=True)
                ]
                # First paragraph is the "25-312 . Heading" line; body is the rest.
                body = "\n".join(paras[1:]).strip()
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
