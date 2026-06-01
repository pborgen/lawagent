"""Louisiana divorce law — La. Civil Code arts. 102-117 (Divorce; Spousal
Support), from the official legis.la.gov.

Louisiana is a civil-law state, so divorce lives in numbered Civil Code
*articles*, not a statute chapter. legis.la.gov addresses each article by an
opaque document id (`Law.aspx?d=<id>`) that isn't derivable from the article
number, so the verified number→id map is pinned here. Article text is in
`#ctl00_PageBody_divLaw` (server-rendered).
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_html, write_statute_section

_LAW_URL = "https://legis.la.gov/legis/Law.aspx?d={d}"
_CITATION = "La. Civ. Code art. {section}"
_ISSUING = "Louisiana State Legislature"
# Verified document ids for the substantive divorce / spousal-support articles
# (CC arts. 102-117; 106-110 are vacant). Ids are stable DB keys, not derivable
# from the article number, so they're pinned (sourced from the folder=67 TOC).
_ARTICLES: dict[str, int] = {
    "102": 108532, "103": 108533, "104": 108534, "105": 108535,
    "111": 108546, "112": 108548, "113": 108549, "114": 108552,
    "115": 108556, "116": 108558, "117": 108560,
}
_TITLE = re.compile(r"Art\.\s*\d+\.\s*([^\n]+)")
_ACTS_TAIL = re.compile(r"\n\s*(?:Amended by\s+)?Acts\s+\d{4}.*$", re.S)


def crawl(
    cfg: StateConfig,
    *,
    out_dir: Path,
    force: bool,
    delay: float,
    max_sections: int | None,
    console: Console,
) -> list[dict[str, str]]:
    import time

    statutes_dir = out_dir / "statutes"
    console.print("crawling [cyan]La. Civ. Code arts. 102-117[/cyan] @ legis.la.gov")

    records: list[dict[str, str]] = []
    for num, doc_id in _ARTICLES.items():
        slug = f"la-ccode-art-{_slugify(num)}"
        url = _LAW_URL.format(d=doc_id)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                div = BeautifulSoup(fetch_html(url), "html.parser").find(
                    id="ctl00_PageBody_divLaw"
                )
                body = div.get_text("\n", strip=True) if div else ""
                tm = _TITLE.search(body)
                title = tm.group(1).strip() if tm else ""
                body = _ACTS_TAIL.sub("", body).strip()  # drop enacting-acts trailer
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
