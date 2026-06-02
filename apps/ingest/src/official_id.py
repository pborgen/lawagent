"""Idaho divorce statutes — Idaho Code Title 32, Chapters 6 (Divorce Actions)
and 7 (maintenance, community property), from legislature.idaho.gov.

Static HTML. Each chapter TOC links sections as /SECT32-<n>/; the body is the
child of `div.pgbrk` whose text starts with the section number (skipping the
breadcrumb that div.pgbrk also carries).
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

_BASE = "https://legislature.idaho.gov"
_CHAPTER_TOC = "https://legislature.idaho.gov/statutesrules/idstat/Title32/T32CH{ch}/"
_CITATION = "Idaho Code § {section}"
_ISSUING = "Idaho Legislature"
_CHAPTERS = (6, 7)
_HREF = re.compile(r"/SECT(32-\d+[A-Za-z]?)/?$")
_BODY = re.compile(r"^\d+-\d+\.")
_TITLE = re.compile(r"^\d+-\d+\.\s+(.+?\.)")


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
    console.print("crawling [cyan]Idaho Code Title 32, Ch. 6-7[/cyan] @ legislature.idaho.gov")

    sections: list[tuple[str, str]] = []
    seen: set[str] = set()
    for ch in _CHAPTERS:
        time.sleep(delay)
        toc = BeautifulSoup(fetch_html(_CHAPTER_TOC.format(ch=ch)), "html.parser")
        for a in toc.find_all("a", href=True):
            m = _HREF.search(a["href"])
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                sections.append((m.group(1), urljoin(_BASE, a["href"])))

    records: list[dict[str, str]] = []
    for num, url in sections:
        slug = f"id-code-{_slugify(num)}"
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                pg = BeautifulSoup(fetch_html(url), "html.parser").select_one("div.pgbrk")
                body = ""
                if pg:
                    inner = [
                        d for d in pg.find_all("div")
                        if _BODY.match(d.get_text(" ", strip=True))
                    ]
                    body = (inner[0] if inner else pg).get_text("\n", strip=True)
                tm = _TITLE.search(body)
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num),
                        title=tm.group(1).strip(".") if tm else "",
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
