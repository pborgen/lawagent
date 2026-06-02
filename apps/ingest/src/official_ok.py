"""Oklahoma divorce statutes — Okla. Stat. Title 43 (Marriage and Family),
from the official OSCN (oscn.net).

Static HTML (legacy latin-1). The Title 43 TOC links each section via an
opaque CiteID; the body lives in `div#oscn-content` (`<p>` after the header).
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

_TOC_URL = "https://www.oscn.net/applications/oscn/index.asp?ftdb=STOKST43"
_CITATION = "Okla. Stat. tit. 43, § {section}"
_ISSUING = "Oklahoma Legislature"
_LINK_NUM = re.compile(r"§\s*([0-9][\w.\-]*)\.")


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
    console.print("crawling [cyan]Okla. Stat. Title 43[/cyan] @ oscn.net")
    toc = BeautifulSoup(fetch_html(_TOC_URL, encoding="latin-1"), "html.parser")

    sections: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in toc.select('a[href*="DeliverDocument"]'):
        m = _LINK_NUM.search(a.get_text(" ", strip=True))
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            sections.append((m.group(1), urljoin(_TOC_URL, a["href"])))

    records: list[dict[str, str]] = []
    for num, url in sections:
        slug = f"ok-stat-43-{_slugify(num)}"
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url, encoding="latin-1"), "html.parser")
                content = ssoup.find(id="oscn-content")
                ps = content.find_all("p") if content else []
                body = "\n\n".join(
                    p.get_text(" ", strip=True).replace("\xa0", " ") for p in ps[1:]
                    if p.get_text(strip=True)
                ).strip()
                title = ssoup.title.get_text(strip=True) if ssoup.title else ""
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
