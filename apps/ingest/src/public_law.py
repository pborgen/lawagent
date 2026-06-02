"""Discovery-driven crawler for `<state>.public.law` statute codes.

public.law mirrors statutes with a consistent *section page* (statute text in
`<section>` tags, name in the `<title>`), but states differ in **navigation**:

    NY  /laws/<root>      -> <root>_article_N      -> <root>_section_M      (2 levels)
    TX  /statutes/<root>  -> _title_ -> _subtitle_ -> _chapter_ -> _section_ (deeper)

So this module splits cleanly:

  * **Shared primitives** (reused by every state): `fetch_html`,
    `check_robots`, `_section_number/_section_title/_section_body`,
    `fetch_and_write_section`, and the generic `run_crawl(discover=...)` loop.
  * **Per-shape discovery** lives next to its crawler: `_discover_article`
    here (NY-style), and the deeper hierarchy in `public_law_tx.py`. A state
    whose navigation differs gets its own discovery fn + a one-line wrapper —
    everything below the navigation is reused.

All of it reuses `fetch_public`'s `_download` (SSL fallbacks),
`render_with_frontmatter`, and `normalize_text` rather than reinventing them.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import FetchSpec, StatuteCode

from ingest.src.fetch_public import (
    USER_AGENT,
    SourceSpec,
    _PDF_IMPORT_ERROR,
    _PDF_KIND,
    _download,
    _fetch_one,
    normalize_text,
    render_with_frontmatter,
)

def public_law_base(subdomain: str, path_prefix: str) -> str:
    """`https://<subdomain>.public.law<path_prefix>` (path_prefix `/laws/` or `/statutes/`)."""
    return f"https://{subdomain}.public.law{path_prefix}"


def fetch_html(url: str, *, encoding: str = "utf-8") -> str:
    """Download a page as text, reusing fetch_public's SSL fallbacks.

    `encoding` defaults to utf-8; pass "latin-1" for legacy sites (e.g. OSCN)
    that serve cp1252/latin-1 and choke a utf-8 decode on 0xa0.
    """
    return _download(url).decode(encoding, errors="replace")


def fetch_pdf_text(url: str, *, browser_ua: bool = False, timeout: int = 60) -> str:
    """Download a PDF and return its extracted text (PyMuPDF via pdf2text).

    Several states serve statute sections only as PDFs (KY, IA, ...). Reuses
    fetch_public's `pdf_bytes_to_markdown` so PDF handling lives in one place.
    """
    from ingest.src.fetch_public import pdf_bytes_to_markdown

    ua = _BROWSER_UA if browser_ua else USER_AGENT
    text = pdf_bytes_to_markdown(_download(url, user_agent=ua, timeout=timeout))
    # Strip pdf2text's markdown scaffolding — the "# <tmpfile>.pdf" title and
    # "## Page N" separators — so it doesn't pollute the statute body.
    lines = [
        ln for ln in text.splitlines()
        if not re.match(r"^#\s+\S*\.pdf\s*$", ln)
        and not re.match(r"^##\s+Page\s+\d+\s*$", ln)
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# A real browser UA + generous timeout, for official sites that gate static
# files on the User-Agent or serve large single-file codes (e.g. iga.in.gov).
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def fetch_html_browser(url: str, *, timeout: int = 60) -> str:
    """Like `fetch_html`, but sends a browser User-Agent (and a longer timeout)."""
    return _download(url, user_agent=_BROWSER_UA, timeout=timeout).decode(
        "utf-8", errors="replace"
    )


def check_robots(subdomain: str, path_prefix: str, console: Console) -> None:
    """Fail loud if a state's robots.txt disallows `path_prefix` for everyone.

    States may use `/laws/` (NY) or `/statutes/` (TX); both must be permitted
    before we crawl. We verified the current ones, but a future state might
    differ — better to stop than to crawl a disallowed path.
    """
    url = f"https://{subdomain}.public.law/robots.txt"
    try:
        body = fetch_html(url)
    except Exception:
        # No robots / unreachable robots — proceed (the section fetches will
        # surface any real access problem).
        return

    disallowed: list[str] = []
    applies = False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            applies = value == "*"
        elif field == "disallow" and applies and value:
            disallowed.append(value)

    if any(path_prefix.startswith(rule) for rule in disallowed):
        raise RuntimeError(
            f"{url} disallows {path_prefix} for '*'; refusing to crawl "
            f"{subdomain}.public.law."
        )


def _links_under(html: str, base_url: str, code_root: str, kind: str) -> list[str]:
    """Absolute URLs of `<code_root>_<kind>_*` children (NY: child directly under root)."""
    soup = BeautifulSoup(html, "html.parser")
    marker = f"{code_root}_{kind}_"
    seen: dict[str, None] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        tail = href.rsplit("/", 1)[-1]
        if tail.startswith(marker):
            seen[urljoin(base_url, href)] = None
    return list(seen)


def links_matching(html: str, base_url: str, code_root: str, substr: str) -> list[str]:
    """Absolute URLs whose tail contains both `code_root` and `substr`, any depth.

    Unlike `_links_under` (prefix match), this finds links anywhere in a
    cumulative slug like `tex._fam._code_title_1_subtitle_c_chapter_6` — needed
    for deeper hierarchies where the marker isn't directly under the root.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, None] = {}
    for anchor in soup.find_all("a", href=True):
        tail = anchor["href"].rsplit("/", 1)[-1]
        if code_root in tail and substr in tail:
            seen[urljoin(base_url, anchor["href"])] = None
    return list(seen)


def _section_number(url: str) -> str:
    """Extract the section number from a section URL, across layouts.

    `..._section_236-a`        -> `236-a`   (NY/TX/CA carry a `_section_` token)
    `fla._stat._61.08`         -> `61.08`   (flat slugs: number is the last
    `ors_107.105`              -> `107.105`   underscore-separated token, which
    `crs_14-10-106`            -> `14-10-106` is never itself underscored)
    """
    tail = url.rsplit("/", 1)[-1]
    if "_section_" in tail:
        return tail.split("_section_", 1)[1]
    return tail.rsplit("_", 1)[-1]


_TITLE_TAIL_YEAR_RE = re.compile(r"\s*\(\d{4}\)\s*$")


def _section_title(html: str) -> str:
    """Human name of the section from the page <title>.

    `<title>N.Y. Domestic Relations Law Section 170 – Action for divorce (2026)</title>`
    -> `Action for divorce`. Falls back to the whole title if the dash split
    is absent.
    """
    soup = BeautifulSoup(html, "html.parser")
    raw = normalize_text(soup.title.get_text()) if soup.title else ""
    # public.law uses an en dash (–) between the section label and its name.
    for sep in (" – ", " — ", " - "):
        if sep in raw:
            raw = raw.split(sep, 1)[1]
            break
    return _TITLE_TAIL_YEAR_RE.sub("", raw).strip()


def _section_body(html: str) -> str:
    """The statute text — public.law renders each paragraph/subdivision as a
    `<section>` element. Join them in document order."""
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[str] = []
    for node in soup.find_all("section"):
        text = normalize_text(node.get_text(" ", strip=True))
        if text:
            blocks.append(text)
    return "\n\n".join(blocks).strip()


def _clean_meta_value(value: str) -> str:
    """Collapse whitespace/newlines so the naive frontmatter writer can't be
    broken by a multi-line value, and drop a trailing period so a citation
    like `§ 236` never becomes `§ 236.`."""
    return normalize_text(value).rstrip(". ").strip()


def write_statute_section(
    *,
    statutes_dir: Path,
    slug: str,
    citation: str,
    title: str,
    section: str,
    jurisdiction: str,
    issuing_body: str,
    source_url: str,
    body: str,
    force: bool,
    console: Console,
) -> dict[str, str]:
    """Write one statute section to a frontmatter `.txt` file.

    The single, shared sink for every crawler — public.law *and* the bespoke
    official-site crawlers (`official_*.py`) — so frontmatter shape,
    metadata-value cleaning, and skip-existing behavior live in one place.
    Metadata values are cleaned; `body` is written as-is to preserve the
    statute's paragraph/subsection structure for chunking.
    """
    output_path = statutes_dir / f"{slug}.txt"
    if output_path.exists() and not force:
        console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
        return {"slug": slug, "url": source_url, "status": "skipped"}
    if not body or not body.strip():
        console.print(f"  [red]failed[/red] {slug}: no statute text")
        return {"slug": slug, "url": source_url, "status": "failed",
                "error": "no statute text"}

    citation = _clean_meta_value(citation)
    metadata = {
        "source_type": "statute",
        "authority_level": "primary",
        "citation": citation,
        "title": _clean_meta_value(title) or citation,
        "section": _clean_meta_value(section),
        "jurisdiction": jurisdiction,
        "issuing_body": _clean_meta_value(issuing_body),
        "source_url": source_url,
    }
    statutes_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_with_frontmatter(metadata, body, suffix=".txt"), encoding="utf-8"
    )
    console.print(f"  fetched [green]{slug}[/green] ({citation})")
    return {"slug": slug, "url": source_url, "status": "fetched"}


def fetch_and_write_section(
    *,
    sec_url: str,
    code: StatuteCode,
    state_name: str,
    statutes_dir: Path,
    out_dir: Path,
    force: bool,
    delay: float,
    console: Console,
) -> dict[str, str]:
    """Fetch one section page, build its frontmatter, and write the file.

    Shared by every state's crawler — the section page format is identical
    across public.law, so only navigation/discovery is state-specific.
    Resumable: skips (no network) when the file already exists and not `force`.
    """
    section = _section_number(sec_url)
    slug = f"{_slugify(code.code_root)}-{_slugify(section)}"
    output_path = statutes_dir / f"{slug}.txt"

    if output_path.exists() and not force:
        console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
        return {"slug": slug, "url": sec_url, "status": "skipped"}

    time.sleep(delay)
    try:
        html = fetch_html(sec_url)
        citation = code.citation_format.format(section=section)
        return write_statute_section(
            statutes_dir=statutes_dir,
            slug=slug,
            citation=citation,
            title=_section_title(html),
            section=section,
            jurisdiction=state_name,
            issuing_body=code.issuing_body or "",
            source_url=sec_url,
            body=_section_body(html),
            force=force,
            console=console,
        )
    except Exception as exc:
        console.print(f"  [red]failed[/red] {slug}: {exc}")
        return {"slug": slug, "url": sec_url, "status": "failed", "error": str(exc)}


def run_crawl(
    *,
    subdomain: str,
    code: StatuteCode,
    state_name: str,
    out_dir: Path,
    force: bool,
    delay: float,
    max_sections: int | None,
    console: Console,
    path_prefix: str,
    discover,
) -> list[dict[str, str]]:
    """Generic crawl: robots-check, run a `discover` strategy, write each section.

    `discover(*, base, code, delay, max_sections, console) -> list[str]` is the
    only state-specific piece — it returns section-page URLs. Everything else
    (robots, paging, per-section fetch+write) is shared.
    """
    check_robots(subdomain, path_prefix, console)
    base = public_law_base(subdomain, path_prefix)
    statutes_dir = out_dir / "statutes"
    statutes_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"crawling code [cyan]{code.code_root}[/cyan] @ {subdomain}.public.law")
    section_urls = discover(
        base=base, code=code, delay=delay, max_sections=max_sections, console=console
    )
    if max_sections is not None:
        section_urls = section_urls[:max_sections]
    console.print(f"  found [bold]{len(section_urls)}[/bold] sections")

    return [
        fetch_and_write_section(
            sec_url=sec_url,
            code=code,
            state_name=state_name,
            statutes_dir=statutes_dir,
            out_dir=out_dir,
            force=force,
            delay=delay,
            console=console,
        )
        for sec_url in section_urls
    ]


def _discover_article(*, base, code: StatuteCode, delay, max_sections, console) -> list[str]:
    """NY-style discovery: code TOC -> article pages -> section links."""
    toc_html = fetch_html(urljoin(base, code.code_root))
    article_urls = _links_under(toc_html, base, code.code_root, "article")
    if code.articles:
        wanted = {a.rsplit("/", 1)[-1] for a in code.articles}
        article_urls = [u for u in article_urls if u.rsplit("/", 1)[-1] in wanted]

    section_urls: list[str] = []
    seen: set[str] = set()
    for article_url in article_urls:
        time.sleep(delay)
        try:
            article_html = fetch_html(article_url)
        except Exception as exc:
            console.print(f"  [red]article failed[/red] {article_url}: {exc}")
            continue
        for sec_url in _links_under(article_html, base, code.code_root, "section"):
            if sec_url not in seen:
                seen.add(sec_url)
                section_urls.append(sec_url)
        if max_sections is not None and len(section_urls) >= max_sections:
            break
    return section_urls


def crawl_public_law(
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
    """Crawl an NY-style (article -> section) code into one file/section."""
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
        discover=_discover_article,
    )


def fetch_specs(
    specs: list[FetchSpec],
    out_dir: Path,
    subdir: str,
    *,
    force: bool,
    include_pdfs: bool,
    console: Console,
) -> list[dict[str, str]]:
    """Download explicit single-URL sources (forms / practice rules).

    Each registry `FetchSpec` is adapted to the existing `SourceSpec` shape
    and run through `fetch_public._fetch_one`, so HTML/PDF extraction and the
    SSL fallbacks are shared with the CT path. Best-effort: a failed or
    bot-blocked URL is recorded, not fatal (many official sites block bots).
    """
    target_dir = out_dir / subdir
    records: list[dict[str, str]] = []
    for fs in specs:
        if fs.kind == _PDF_KIND and not include_pdfs:
            continue
        if fs.kind == _PDF_KIND and _PDF_IMPORT_ERROR is not None:
            console.print(f"  [red]skip[/red] {fs.slug}: PDF support unavailable")
            records.append({"slug": fs.slug, "url": fs.url, "status": "failed",
                            "error": "PDF support unavailable"})
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{fs.slug}.md"
        if output_path.exists() and not force:
            console.print(f"  skipping [yellow]{fs.slug}[/yellow] (exists)")
            records.append({"slug": fs.slug, "url": fs.url, "status": "skipped"})
            continue

        spec = SourceSpec(
            slug=fs.slug,
            kind=fs.kind,
            url=fs.url,
            output_path=str(output_path.relative_to(out_dir)),
            metadata={k: _clean_meta_value(v) for k, v in fs.metadata.items()},
        )
        try:
            content = _fetch_one(spec)
            output_path.write_text(content, encoding="utf-8")
            console.print(f"  fetched [green]{fs.slug}[/green]")
            records.append({"slug": fs.slug, "url": fs.url, "status": "fetched"})
        except Exception as exc:
            console.print(f"  [red]failed[/red] {fs.slug}: {exc}")
            records.append({"slug": fs.slug, "url": fs.url, "status": "failed",
                            "error": str(exc)})
    return records


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


__all__ = [
    "crawl_public_law",
    "fetch_specs",
    "run_crawl",
    "fetch_html",
    "check_robots",
    "links_matching",
    "fetch_and_write_section",
    "write_statute_section",
    "fetch_html_browser",
    "fetch_pdf_text",
    "USER_AGENT",
]
