"""North Carolina divorce statutes — N.C. Gen. Stat. Chapter 50 (Divorce and
Alimony), from the official ncleg.gov.

Static HTML. The Chapter 50 TOC links to per-section "BySection" pages; each
is a flat `<body>` of `<p>` elements — the first holds the heading
(`GSDocumentHeader` anchor), the rest the statute text, with a trailing
session-law History Note we drop. Numbering is sparse, so we enumerate from
the TOC rather than guessing.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_TOC_URL = "https://www.ncleg.gov/Laws/GeneralStatuteSections/Chapter50"
_SECTION_URL = (
    "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/"
    "Chapter_50/GS_{num}.html"
)
_CITATION = "N.C. Gen. Stat. § {section}"
_ISSUING = "North Carolina General Assembly"
_HREF = re.compile(r"/HTML/BySection/Chapter_50/GS_(50-[\w.]+)\.html")
_TITLE = re.compile(r"§\s*[\w.\-]+\.\s*(.*)")


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
    console.print("crawling [cyan]N.C. Gen. Stat. Chapter 50[/cyan] @ ncleg.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    numbers: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        m = _HREF.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            numbers.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in numbers:
        slug = f"nc-gs-{_slugify(num)}"
        url = _SECTION_URL.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                for note in ssoup.find_all("a", attrs={"name": "HistoryNote"}):
                    note.decompose()
                hdr = ssoup.find("a", attrs={"name": "GSDocumentHeader"})
                title = ""
                if hdr and (span := hdr.find_next("span")):
                    tm = _TITLE.match(span.get_text(" ", strip=True))
                    title = tm.group(1) if tm else ""
                paras = ssoup.find_all("p")
                body = "\n\n".join(
                    re.sub(r"\s+", " ", p.get_text(" ", strip=True).replace("\xa0", " "))
                    for p in paras[1:]
                ).strip()
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir,
                        slug=slug,
                        citation=_CITATION.format(section=num),
                        title=title,
                        section=num,
                        jurisdiction=cfg.name,
                        issuing_body=_ISSUING,
                        source_url=url,
                        body=body,
                        force=force,
                        console=console,
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
