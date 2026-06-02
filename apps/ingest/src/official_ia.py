"""Iowa divorce statutes — Iowa Code Chapter 598 (Dissolution of Marriage),
from the official Iowa Legislature (legis.iowa.gov).

PDF-based. The chapter PDF (598.pdf) carries a TOC we use to enumerate
section numbers; each section is then fetched as its own PDF
(/docs/code/{section}.pdf) and its text extracted.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, fetch_pdf_text, write_statute_section

_CHAPTER_PDF = "https://www.legis.iowa.gov/docs/code/598.pdf"
_SECTION_PDF = "https://www.legis.iowa.gov/docs/code/{num}.pdf"
_CITATION = "Iowa Code § {section}"
_ISSUING = "Iowa Legislature"
_NUM = re.compile(r"(?m)^\s*(598\.\d+[A-Z]?)\b")
# Heading line in a section PDF: "598.21A Orders for spousal support."
_TITLE = re.compile(r"^\s*598\.\d+[A-Z]?\s+(.+?)\.?\s*$", re.M)


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
    console.print("crawling [cyan]Iowa Code Chapter 598[/cyan] @ legis.iowa.gov")

    chapter_text = fetch_pdf_text(_CHAPTER_PDF, browser_ua=True)
    nums: list[str] = []
    seen: set[str] = set()
    for m in _NUM.finditer(chapter_text):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"ia-code-{_slugify(num)}"
        url = _SECTION_PDF.format(num=num)
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": url, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                text = fetch_pdf_text(url, browser_ua=True)
                tm = _TITLE.search(text)
                records.append(
                    write_statute_section(
                        statutes_dir=statutes_dir, slug=slug,
                        citation=_CITATION.format(section=num),
                        title=tm.group(1).strip() if tm else "",
                        section=num, jurisdiction=cfg.name, issuing_body=_ISSUING,
                        source_url=url, body=text, force=force, console=console,
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
