"""New Hampshire divorce statutes — N.H. Rev. Stat. (RSA) Chapter 458
(Annulment, Divorce and Separation), from gc.nh.gov.

Static HTML. The merged chapter page inlines every section as
`<h3>Section 458:N</h3>` + `<b>458:N Heading. –</b>` + `<codesect>body</codesect>`,
so one fetch yields the whole chapter. NH section numbers keep a colon
(458:19); the per-section URL maps colon -> hyphen.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_MERGED_URL = "https://gc.nh.gov/rsa/html/XLIII/458/458-mrg.htm"
_SECTION_URL = "https://gc.nh.gov/rsa/html/XLIII/458/458-{n}.htm"
_CITATION = "N.H. Rev. Stat. § {section}"
_ISSUING = "New Hampshire General Court"
_H3 = re.compile(r"Section\s+(458:[\w\-]+)")


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
    console.print("crawling [cyan]N.H. Rev. Stat. Chapter 458[/cyan] @ gc.nh.gov")
    soup = BeautifulSoup(fetch_html(_MERGED_URL), "html.parser")

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for h3 in soup.find_all("h3"):
        m = _H3.match(h3.get_text(" ", strip=True))
        if not m or m.group(1) in seen:
            continue
        num = m.group(1)
        seen.add(num)
        cs = h3.find_next("codesect")
        body = cs.get_text(" ", strip=True).replace("\xa0", " ") if cs else ""
        b = h3.find_next("b")
        title = ""
        if b:
            bt = b.get_text(" ", strip=True).replace("\xa0", " ")
            title = re.sub(rf"^{re.escape(num)}\s*", "", bt).strip().strip("–").strip(" .")
        records.append(
            write_statute_section(
                statutes_dir=statutes_dir,
                slug=f"nh-rsa-{_slugify(num)}",
                citation=_CITATION.format(section=num),
                title=title,
                section=num,
                jurisdiction=cfg.name,
                issuing_body=_ISSUING,
                source_url=_SECTION_URL.format(n=num.replace(":", "-")),
                body=body,
                force=force,
                console=console,
            )
        )
        if max_sections is not None and len(records) >= max_sections:
            break
    return records


__all__ = ["crawl"]
