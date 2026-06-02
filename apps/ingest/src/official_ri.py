"""Rhode Island divorce statutes — R.I. Gen. Laws Title 15, Chapter 15-5
(Divorce and Separation), from webserver.rilegislature.gov.

Static HTML. The chapter INDEX links each section as 15-5-N.htm; the body
text begins at the bold `§ 15-5-N. Heading` line (after a breadcrumb).
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_BASE = "https://webserver.rilegislature.gov/Statutes/TITLE15/15-5/"
_TOC_URL = _BASE + "INDEX.htm"
_CITATION = "R.I. Gen. Laws § {section}"
_ISSUING = "Rhode Island General Assembly"
_HREF = re.compile(r"^(15-5-[\d.]+)\.htm$", re.I)


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
    console.print("crawling [cyan]R.I. Gen. Laws Chapter 15-5[/cyan] @ rilegislature.gov")
    toc = BeautifulSoup(fetch_html(_TOC_URL), "html.parser")

    nums: list[str] = []
    seen: set[str] = set()
    for a in toc.find_all("a", href=True):
        tail = a["href"].rsplit("/", 1)[-1]
        m = _HREF.match(tail)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"ri-genlaws-{_slugify(num)}"
        url = _BASE + f"{num}.htm"
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                soup = BeautifulSoup(fetch_html(url), "html.parser")
                full = soup.get_text("\n", strip=True).replace("\xa0", " ")
                i = full.find(f"§ {num}")
                body = full[i:].strip() if i >= 0 else full
                first = body.split("\n", 1)[0]
                title = re.sub(rf"^§\s*{re.escape(num)}\.\s*", "", first).strip().rstrip(".")
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
