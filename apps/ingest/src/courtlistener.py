"""Bounded case-law seeding from CourtListener (Free Law Project).

Statutes and forms carry most of the value; case law is a *seed* of the
landmark family-law opinions for a state, not an exhaustive ingest. So this
is deliberately capped (`max_cases`), keyed (needs `COURTLISTENER_API_TOKEN`),
and skips cleanly when the token is absent.

CourtListener REST v4:
    GET /api/rest/v4/search/?type=o&court=<ids>&q=<query>   -> opinion clusters
    GET /api/rest/v4/opinions/<id>/                          -> opinion text

Each opinion becomes a `case-*.md` file whose frontmatter holds the proper
reporter citation, so chunking never has to guess it from the first line.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rich.console import Console

from corpus import StateConfig
from settings import get_settings

from ingest.src.fetch_public import USER_AGENT, html_to_markdownish, render_with_frontmatter

_API_ROOT = "https://www.courtlistener.com/api/rest/v4"
_TIMEOUT = 30
# Family-law focus so we seed relevant opinions rather than a court's whole docket.
_DEFAULT_QUERY = "divorce OR alimony OR maintenance OR custody OR equitable distribution"


def _get_json(url: str, token: str) -> dict:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Authorization": f"Token {token}"},
    )
    with urlopen(request, timeout=_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _slugify(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text)
    return "-".join(filter(None, out.split("-")))[:80]


def fetch_courtlistener_cases(
    state: StateConfig,
    out_dir: Path,
    *,
    max_cases: int,
    force: bool,
    console: Console,
) -> list[dict[str, str]]:
    """Seed up to `max_cases` opinions for the state's appellate courts.

    No-op (returns []) when no token is configured or no courts are listed.
    """
    token = get_settings().courtlistener_api_token
    if not token:
        console.print(
            "[yellow]skip case law[/yellow]: COURTLISTENER_API_TOKEN is not set."
        )
        return []
    if not state.courtlistener_courts:
        console.print(f"[yellow]skip case law[/yellow]: no courts listed for {state.slug}.")
        return []

    cases_dir = out_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "type": "o",
        "court": ",".join(state.courtlistener_courts),
        "q": _DEFAULT_QUERY,
        "order_by": "score desc",
    }
    search_url = f"{_API_ROOT}/search/?{urlencode(params)}"

    records: list[dict[str, str]] = []
    try:
        page = _get_json(search_url, token)
    except (HTTPError, URLError) as exc:
        console.print(f"[red]case search failed[/red]: {exc}")
        return [{"slug": "search", "url": search_url, "status": "failed", "error": str(exc)}]

    for result in (page.get("results") or [])[:max_cases]:
        name = result.get("caseName") or result.get("caseNameFull") or "opinion"
        date = result.get("dateFiled") or ""
        citation = "; ".join(result.get("citation") or []) or name
        opinion_id = result.get("id")
        cluster_url = result.get("absolute_url") or ""
        full_url = f"https://www.courtlistener.com{cluster_url}" if cluster_url else search_url

        slug = f"case-{_slugify(name)}"
        output_path = cases_dir / f"{slug}.md"
        if output_path.exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": full_url, "status": "skipped"})
            continue

        try:
            text = _opinion_text(opinion_id, token)
            if not text:
                raise ValueError("opinion has no retrievable text")
            metadata = {
                "source_type": "case",
                "authority_level": "primary",
                "citation": citation,
                "title": name,
                "date": date,
                "jurisdiction": state.name,
                "issuing_body": result.get("court") or "",
                "source_url": full_url,
            }
            content = render_with_frontmatter(metadata, text, suffix=".md")
            output_path.write_text(content, encoding="utf-8")
            console.print(f"  fetched [green]{slug}[/green] ({citation})")
            records.append({"slug": slug, "url": full_url, "status": "fetched"})
        except Exception as exc:
            console.print(f"  [red]failed[/red] {slug}: {exc}")
            records.append({"slug": slug, "url": full_url, "status": "failed", "error": str(exc)})

    return records


def _opinion_text(opinion_id: int | None, token: str) -> str:
    """Plain text of an opinion, falling back to HTML→markdown."""
    if opinion_id is None:
        return ""
    data = _get_json(f"{_API_ROOT}/opinions/{opinion_id}/", token)
    plain = (data.get("plain_text") or "").strip()
    if plain:
        return plain
    for key in ("html_with_citations", "html", "html_lawbox", "html_columbia"):
        if data.get(key):
            return html_to_markdownish(data[key]).strip()
    return ""


__all__ = ["fetch_courtlistener_cases"]
