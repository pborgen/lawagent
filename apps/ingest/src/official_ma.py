"""Massachusetts divorce statutes — M.G.L. Chapter 208 (Divorce), from the
official malegislature.gov.

Static HTML. The chapter page links to each section; the section page holds
its text as `<p>` tags inside the content `div.col-xs-12`, with the heading in
an `<h2>` of the form "Section N:Title".
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

_BASE = "https://malegislature.gov"
_CHAPTER_TOC = "https://malegislature.gov/Laws/GeneralLaws/PartII/TitleIII/Chapter208"
_CITATION = "Mass. Gen. Laws ch. 208, § {section}"
_ISSUING = "Massachusetts General Court"
_HREF = re.compile(r"/Chapter208/Section(\S+)$")
_SEC_P = re.compile(r"^Section\s+\S+")


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
    console.print("crawling [cyan]Mass. Gen. Laws ch. 208[/cyan] @ malegislature.gov")
    toc = BeautifulSoup(fetch_html(_CHAPTER_TOC), "html.parser")

    sections: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in toc.select("a[href*='/Chapter208/Section']"):
        m = _HREF.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            sections.append((m.group(1), urljoin(_BASE, a["href"])))

    records: list[dict[str, str]] = []
    for num, url in sections:
        slug = f"ma-mgl-208-{_slugify(num)}"
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                title = ""
                for h2 in ssoup.find_all("h2"):
                    t = h2.get_text(" ", strip=True)
                    if t.startswith("Section") and ":" in t:
                        title = t.split(":", 1)[1].strip()
                        break
                body = ""
                for p in ssoup.find_all("p"):
                    if _SEC_P.match(p.get_text(strip=True)):
                        container = p.find_parent("div", class_="col-xs-12") or p.parent
                        body = "\n\n".join(
                            pp.get_text(" ", strip=True)
                            for pp in container.find_all("p")
                            if pp.get_text(strip=True)
                        )
                        break
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
