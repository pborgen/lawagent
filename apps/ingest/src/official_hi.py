"""Hawaii divorce statutes — Haw. Rev. Stat. Chapter 580 (Annulment, Divorce
and Separation), from data.capitol.hawaii.gov.

Static per-section .htm files (the www. host is Cloudflare-blocked; the data.
host serves the identical tree). The chapter TOC lists section numbers; we map
each to its zero-padded filename. Body = the RegularParagraphs/oneParagraph
`<p>` after the first §-paragraph, excluding XNotes annotation blocks.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_DIR = "https://data.capitol.hawaii.gov/hrscurrent/Vol12_Ch0501-0588/HRS0580/"
_TOC_URL = _DIR + "HRS_0580-.htm"
_CITATION = "Haw. Rev. Stat. § {section}"
_ISSUING = "Hawaii State Legislature"
_NUM = re.compile(r"\b(580-\d+(?:\.\d+)?)\b")
_HEAD = re.compile(r"§\s*([\d.\-]+)\s+(.+?\.)\s")
_BODY_CLASSES = {"RegularParagraphs", "oneParagraph"}


def _filename(num: str) -> str:
    """`580-47` -> HRS_0580-0047.htm ; `580-10.5` -> HRS_0580-0010_0005.htm."""
    sec = num.split("-", 1)[1]
    if "." in sec:
        main, dec = sec.split(".", 1)
        tail = f"{int(main):04d}_{int(dec):04d}"
    else:
        tail = f"{int(sec):04d}"
    return f"HRS_0580-{tail}.htm"


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
    console.print("crawling [cyan]Haw. Rev. Stat. Chapter 580[/cyan] @ data.capitol.hawaii.gov")
    toc_text = BeautifulSoup(fetch_html(_TOC_URL), "html.parser").get_text(" ")

    nums: list[str] = []
    seen: set[str] = set()
    for m in _NUM.finditer(toc_text):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"hi-hrs-{_slugify(num)}"
        url = _DIR + _filename(num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(fetch_html(url), "html.parser")
                paras = ssoup.find_all("p")
                started = False
                pieces: list[str] = []
                title = ""
                for p in paras:
                    classes = set(p.get("class") or [])
                    text = p.get_text(" ", strip=True).replace("\xa0", " ")
                    if not started:
                        if text.startswith("§"):
                            started = True
                            hm = _HEAD.search(text + " ")
                            if hm:
                                title = hm.group(2).strip(".")
                        else:
                            continue
                    if classes & _BODY_CLASSES:
                        pieces.append(re.sub(r"\s+", " ", text))
                body = "\n\n".join(pc for pc in pieces if pc).strip()
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
