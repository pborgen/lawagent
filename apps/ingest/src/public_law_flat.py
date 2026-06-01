"""Flat-section public.law crawler (FL, OR, CO, NV).

These states nest *containers* (titles/chapters/articles/sub-chapters) like
the others, but their leaf section slugs are **flat** and carry no
`_section_` token — they're just `<section_prefix>_<number>`:

    Florida   fla._stat._61.08
    Oregon    ors_107.105
    Colorado  crs_14-10-106
    Nevada    nrs_125.180

and the section slug is NOT nested under the container slug, so the
hierarchical/article crawlers (which key off `_section_` and cumulative
prefixes) can't find them. The fix is small: identify section links by the
registry's `section_prefix` followed by a digit. The container that lists
the sections is given directly as a crawl seed (`code.articles`), so no
descent is needed. Everything else — robots, section-page parsing, the
fetch/write loop — is reused from `public_law.run_crawl`.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StatuteCode

from ingest.src.public_law import fetch_html, run_crawl


def _section_links_flat(html: str, base_url: str, section_prefix: str) -> list[str]:
    """Absolute URLs of links whose slug is `<section_prefix>_<digit...>`.

    That digit test is what separates a section (`ors_107.105`) from a
    container (`ors_chapter_107`, `ors_title_11`) that shares the prefix.
    """
    marker = f"{section_prefix}_"
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, None] = {}
    for anchor in soup.find_all("a", href=True):
        tail = anchor["href"].rsplit("/", 1)[-1]
        if tail.startswith(marker) and tail[len(marker):][:1].isdigit():
            out[urljoin(base_url, anchor["href"])] = None
    return list(out)


def _discover_flat(*, base, code: StatuteCode, delay, max_sections, console) -> list[str]:
    """Fetch each seed container and harvest its flat section links."""
    if not code.section_prefix:
        raise ValueError(
            f"flat_section layout for {code.code_root!r} requires `section_prefix`."
        )
    seeds = [urljoin(base, slug) for slug in (code.articles or [code.code_root])]
    section_urls: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        time.sleep(delay)
        try:
            html = fetch_html(seed)
        except Exception as exc:
            console.print(f"  [red]container failed[/red] {seed}: {exc}")
            continue
        for sec_url in _section_links_flat(html, base, code.section_prefix):
            if sec_url not in seen:
                seen.add(sec_url)
                section_urls.append(sec_url)
        if max_sections is not None and len(section_urls) >= max_sections:
            break
    return section_urls


def crawl_public_law_flat(
    *,
    subdomain: str,
    code: StatuteCode,
    state_name: str,
    out_dir: Path,
    force: bool,
    delay: float,
    max_sections: int | None,
    console: Console,
) -> list[dict[str, str]]:
    """Crawl a flat-section code (sections listed directly under seed containers)."""
    return run_crawl(
        subdomain=subdomain,
        code=code,
        state_name=state_name,
        out_dir=out_dir,
        force=force,
        delay=delay,
        max_sections=max_sections,
        console=console,
        path_prefix=code.base_path,
        discover=_discover_flat,
    )


__all__ = ["crawl_public_law_flat"]
