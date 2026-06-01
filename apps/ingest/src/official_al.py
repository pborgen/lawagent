"""Alabama divorce statutes — Ala. Code Title 30, Chapter 2 (Divorce and
Alimony), from the official Alabama Legislature (alison.legislature.state.al.us).

The site is a JS SPA with no server-rendered statute text, but its data comes
from a public, unauthenticated GraphQL endpoint. We enumerate Chapter 2
section IDs from the code-tree query, then fetch each section's HTML `content`
by displayId. (The only state so far that needs an HTTP POST / JSON API.)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from rich.console import Console

from corpus import StateConfig

from ingest.src.public_law import _slugify, write_statute_section

_GQL_URL = "https://alison.legislature.state.al.us/graphql"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_CITATION = "Ala. Code § {section}"
_ISSUING = "Alabama Legislature"
_CHAPTER = "30-2-"

_TITLES_QUERY = "query{ titles: codeOfAlabamaTitles }"
_SECTION_QUERY = (
    "query($displayId:String!){codesOfAlabama("
    "where:{type:{eq:Section},displayId:{eq:$displayId}},versions:true)"
    "{data{displayId title content history}}}"
)


def _graphql(query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = Request(
        _GQL_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": _UA},
        method="POST",
    )
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


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
    console.print("crawling [cyan]Ala. Code Title 30, Ch. 2[/cyan] @ alison.legislature.state.al.us")

    tree = _graphql(_TITLES_QUERY)
    blob = str(tree.get("data", {}).get("titles", ""))
    nums: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"Section (30-2-\d+)", blob):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            nums.append(m.group(1))

    records: list[dict[str, str]] = []
    for num in nums:
        slug = f"al-code-{_slugify(num)}"
        src = f"https://alison.legislature.state.al.us/code-of-alabama?title=30&section={num}"
        if (statutes_dir / f"{slug}.txt").exists() and not force:
            console.print(f"  skipping [yellow]{slug}[/yellow] (exists)")
            records.append({"slug": slug, "url": src, "status": "skipped"})
        else:
            time.sleep(delay)
            try:
                d = _graphql(_SECTION_QUERY, {"displayId": num})
                data = (d.get("data", {}).get("codesOfAlabama", {}) or {}).get("data") or []
                body = ""
                title = ""
                if data:
                    item = data[0]
                    body = BeautifulSoup(item.get("content") or "", "html.parser").get_text(
                        "\n", strip=True
                    )
                    title = re.sub(
                        rf"^Section\s+{re.escape(num)}\s*", "", item.get("title") or ""
                    ).strip()
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
