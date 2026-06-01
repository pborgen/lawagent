"""Maryland divorce statutes — Md. Code, Family Law Article, Title 7 (Divorce)
and Title 11 (Alimony), from the official mgaleg.maryland.gov.

Static HTML body in `#StatuteText`, but there's no scrapeable in-page TOC —
the site exposes a `GetNext` JSON endpoint that returns the following section
code, so we walk each title from its first section until the code leaves the
title.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_STATUTE_URL = (
    "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText"
    "?article=gfl&section={section}"
)
_GETNEXT_URL = (
    "https://mgaleg.maryland.gov/mgawebsite/api/Laws/GetNext"
    "?articleCode=gfl&sectionCode={section}&enactments=False"
)
_CITATION = "Md. Code, Fam. Law § {section}"
_ISSUING = "Maryland General Assembly"
# Family Law titles that make up the divorce corpus: 7 Divorce, 11 Alimony.
_TITLES = ("7", "11")


def _walk_title(prefix: str, delay: float, console: Console) -> list[str]:
    """Section codes in a title, via the GetNext endpoint, starting at N-101."""
    nums: list[str] = []
    cur = f"{prefix}-101"
    seen: set[str] = set()
    while cur and cur.startswith(f"{prefix}-") and cur not in seen:
        seen.add(cur)
        nums.append(cur)
        time.sleep(delay)
        try:
            nxt = json.loads(fetch_html(_GETNEXT_URL.format(section=cur)))
        except Exception as exc:
            console.print(f"  [red]GetNext failed[/red] {cur}: {exc}")
            break
        # GetNext returns either a bare JSON string ("7-103") or a list.
        if isinstance(nxt, list):
            cur = nxt[0] if nxt else None
        elif isinstance(nxt, str):
            cur = nxt or None
        else:
            cur = None
    return nums


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
    console.print("crawling [cyan]Md. Code, Fam. Law Titles 7 & 11[/cyan] @ mgaleg.maryland.gov")

    nums: list[str] = []
    for prefix in _TITLES:
        nums.extend(_walk_title(prefix, delay, console))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"md-flaw-{_slugify(num)}"
        url = _STATUTE_URL.format(section=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                html = fetch_html(url)
                body = ""
                if "File Not Found" not in html:
                    st = BeautifulSoup(html, "html.parser").select_one("#StatuteText")
                    if st:
                        for junk in st.select(".btn-group, button"):
                            junk.decompose()
                        body = st.get_text("\n", strip=True).replace("\xa0", " ")
                        body = re.sub(r"^Article\s*-\s*Family Law\s*", "", body).strip()
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num), title="",
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
