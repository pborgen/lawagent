"""Texas-shaped public.law crawler.

Texas diverges from the NY layout in *navigation only*:

  * URL scheme is `/statutes/` (not `/laws/`).
  * The hierarchy is deeper and the slugs are cumulative:
        tex._fam._code
          _title_1 -> _title_1_subtitle_c -> ..._chapter_6 -> ..._section_6.001

The section *page* (statute text + title) is identical to every other state,
so this module only supplies a discovery strategy and a one-line wrapper —
the robots check, per-section fetch/parse/write, and paging are all reused
from `public_law.run_crawl`. Other states with the same deep `/statutes/`
shape can reuse `crawl_public_law_tx` via the registry's `layout` field.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urljoin

from rich.console import Console

from corpus import StatuteCode

from ingest.src.public_law import fetch_html, links_matching, run_crawl

# Slug fragments that mark a *container* page (one that lists deeper pages),
# as opposed to a leaf `_section_` page.
_CONTAINER_MARKERS = (
    "_title_",
    "_subtitle_",
    "_subchapter_",
    "_chapter_",
    "_part_",
    "_division_",
    "_article_",
)


def _tail(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def _container_links(html: str, base: str, code_root: str, current_tail: str) -> list[str]:
    """Deeper container pages linked from `html`.

    Cumulative slugs mean a child's tail starts with its parent's tail, so we
    keep only links that extend `current_tail` — that walks strictly downward
    and ignores breadcrumb links back up to parents/siblings.
    """
    out: dict[str, None] = {}
    for marker in _CONTAINER_MARKERS:
        for url in links_matching(html, base, code_root, marker):
            tail = _tail(url)
            if "_section_" in tail:
                continue
            if tail != current_tail and tail.startswith(current_tail):
                out[url] = None
    return list(out)


def _discover_hierarchical(*, base, code: StatuteCode, delay, max_sections, console) -> list[str]:
    """Depth-first walk down the title/subtitle/chapter tree, collecting sections.

    Starts at the registry's `articles` (treated as container seed slugs, e.g.
    a dissolution subtitle) if given, else the whole code root.
    """
    seeds = (
        [urljoin(base, slug) for slug in code.articles]
        if code.articles
        else [urljoin(base, code.code_root)]
    )
    stack = list(seeds)
    visited: set[str] = set()
    section_urls: list[str] = []
    seen_sec: set[str] = set()

    while stack:
        url = stack.pop()
        if url in visited:
            continue
        visited.add(url)
        time.sleep(delay)
        try:
            html = fetch_html(url)
        except Exception as exc:
            console.print(f"  [red]page failed[/red] {url}: {exc}")
            continue

        for sec_url in links_matching(html, base, code.code_root, "_section_"):
            if sec_url not in seen_sec:
                seen_sec.add(sec_url)
                section_urls.append(sec_url)
        if max_sections is not None and len(section_urls) >= max_sections:
            break

        for child in _container_links(html, base, code.code_root, _tail(url)):
            if child not in visited:
                stack.append(child)

    return section_urls


def crawl_public_law_tx(
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
    """Crawl a Texas-style (`/statutes/`, deep hierarchy) code into one file/section."""
    return run_crawl(
        subdomain=subdomain,
        code=code,
        state_name=state_name,
        out_dir=out_dir,
        force=force,
        delay=delay,
        max_sections=max_sections,
        console=console,
        path_prefix="/statutes/",
        discover=_discover_hierarchical,
    )


__all__ = ["crawl_public_law_tx"]
