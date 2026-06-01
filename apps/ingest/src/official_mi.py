"""Michigan divorce statutes — MCL Chapter 552 (Divorce), from the official
legislature.mi.gov.

Static HTML. The flat chapter index lists every section; each section page
holds its text in `div.sectionWrapper` (`<p>` tags) with the heading in
`h1.h4`. TOC links go through /Home/GetObject; we rewrite to the renderable
/Laws/MCL page.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_TOC_URL = "https://www.legislature.mi.gov/Laws/Index?ObjectName=mcl-chap552"
_SECTION_URL = "https://www.legislature.mi.gov/Laws/MCL?objectName={obj}"
_CITATION = "Mich. Comp. Laws § {section}"
_ISSUING = "Michigan Legislature"
_OBJ = re.compile(r"ObjectName=(mcl-552-[0-9a-z]+)", re.I)


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
    console.print("crawling [cyan]Mich. Comp. Laws Chapter 552[/cyan] @ legislature.mi.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    objs: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        m = _OBJ.search(a["href"])
        if m and m.group(1).lower() not in seen:
            seen.add(m.group(1).lower())
            objs.append(m.group(1).lower())

    records: list[dict[str, str]] = []
    for obj in objs:
        num = "552." + obj[len("mcl-552-"):]
        slug = f"mi-mcl-{_slugify(num)}"
        url = _SECTION_URL.format(obj=obj)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                wrap = BeautifulSoup(fetch_html(url), "html.parser").select_one(
                    "div.sectionWrapper"
                )
                title = ""
                body = ""
                if wrap:
                    h = wrap.select_one("h1.h4")
                    if h:
                        ht = h.get_text(" ", strip=True)
                        title = ht.split(None, 1)[1] if " " in ht else ht
                    body = "\n".join(
                        p.get_text(" ", strip=True) for p in wrap.find_all("p")
                    )
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
