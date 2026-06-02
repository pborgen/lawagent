"""Alaska divorce statutes — Alaska Stat. Chapter 25.24 (Divorce and
Dissolution of Marriage), from akleg.gov.

The human-facing page is a JS shell, but its `?media=` endpoints return static
latin-1 HTML. We enumerate sections from the TOC endpoint, then fetch each
section's print view (`div.statute`).
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_TOC_URL = "https://www.akleg.gov/basis/statutes.asp?media=js&type=TOC&title=25.24"
_PRINT_URL = "https://www.akleg.gov/basis/statutes.asp?media=print&secStart={n}&secEnd={n}"
_SRC_URL = "https://www.akleg.gov/basis/statutes.asp#{n}"
_CITATION = "Alaska Stat. § {section}"
_ISSUING = "Alaska State Legislature"
_NUM = re.compile(r"25\.24\.\d+")


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
    console.print("crawling [cyan]Alaska Stat. Chapter 25.24[/cyan] @ akleg.gov")
    toc = fetch_html(_TOC_URL, encoding="latin-1")
    nums: list[str] = []
    seen: set[str] = set()
    for m in _NUM.finditer(toc):
        if m.group(0) not in seen:
            seen.add(m.group(0))
            nums.append(m.group(0))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"ak-stat-{_slugify(num)}"
        src = _SRC_URL.format(n=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": src, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                ssoup = BeautifulSoup(
                    fetch_html(_PRINT_URL.format(n=num), encoding="latin-1"), "html.parser"
                )
                st = ssoup.select_one("div.statute")
                body = st.get_text(" ", strip=True) if st else ""
                title = ""
                if st and (b := st.find("b")):
                    bt = b.get_text(" ", strip=True)
                    title = re.sub(rf"^Sec\.\s*{re.escape(num)}\.\s*", "", bt).strip().rstrip(".")
                # Skip repealed/renumbered stubs.
                if body.lstrip().startswith("["):
                    records.append({"slug": slug, "url": src, "status": "skipped"})
                    continue
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num), title=title,
                        section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                        source_url=src, body=body, force=force, console=console,
                    )
                )
            except Exception as exc:
                console.print(f"  [red]failed[/red] {slug}: {exc}")
                records.append({"slug": slug, "url": src, "status": "failed",
                                "error": str(exc)})
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
