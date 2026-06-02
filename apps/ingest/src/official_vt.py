"""Vermont divorce statutes — Vt. Stat. Title 15, Chapter 11 (Annulment and
Divorce), from legislature.vermont.gov.

Static HTML. The chapter TOC links each section as /section/15/011/<5-digit>;
the body is `ul.statutes-detail`, heading the first bold line ("§ 751. ...").
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_TOC_URL = "https://legislature.vermont.gov/statutes/chapter/15/011"
_SECTION_URL = "https://legislature.vermont.gov/statutes/section/15/011/{pad}"
_CITATION = "Vt. Stat. tit. 15, § {section}"
_ISSUING = "Vermont General Assembly"
_HREF = re.compile(r"/statutes/section/15/011/0*(\d+)")
_TITLE = re.compile(r"§\s*\d+\.\s*(.+)")


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
    console.print("crawling [cyan]Vt. Stat. Title 15, Ch. 11[/cyan] @ legislature.vermont.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    nums: list[str] = []
    seen: set[str] = set()
    for a in toc.select("a[href*='/statutes/section/15/011/']"):
        m = _HREF.search(a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"vt-stat-15-{_slugify(num)}"
        url = _SECTION_URL.format(pad=num.zfill(5))
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                detail = BeautifulSoup(fetch_html(url), "html.parser").select_one(
                    "ul.statutes-detail"
                )
                body = detail.get_text("\n", strip=True) if detail else ""
                title = ""
                if detail and (b := detail.find("b")):
                    tm = _TITLE.search(b.get_text(" ", strip=True))
                    title = tm.group(1).strip() if tm else ""
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
