"""Per-state source registry — the single definition of where each state's
law comes from.

A *state* entry names its public.law subdomain (for statute crawling), the
statute codes to crawl with their citation formats, optional explicit
form/practice-rule fetch specs, and CourtListener court IDs for case law.
Declared in `config/states.yaml`; this module loads and validates it.

The canonical identifier everywhere is the slug (`ny`), not the display
name. `get_state()` accepts either and resolves to the slug. Pair this with
`llm.collection_for(slug)` to pick the state's pgvector collection.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel

from settings import get_settings


class StatuteCode(BaseModel):
    """One statute code to crawl from public.law for a state."""

    code_root: str  # public.law law path, e.g. "n.y._domestic_relations_law"
    citation_format: str  # "N.Y. Dom. Rel. Law § {section}" — must contain {section}
    title: Optional[str] = None
    issuing_body: Optional[str] = None
    # URL path segment public.law serves this state under: "/laws/" (NY),
    # "/statutes/" (TX, FL, OR, CO, NV), or "/codes/" (CA).
    base_path: str = "/laws/"
    # public.law navigation shape -> which crawler handles it:
    #   "ny_article"      = code -> _article_ -> _section_              (NY)
    #   "tx_hierarchical" = deep cumulative title/subtitle/chapter tree,
    #                       leaf slugs carry a "_section_" token        (TX, CA)
    #   "flat_section"    = containers nest, but leaf sections are flat
    #                       "<section_prefix>_<number>" slugs with NO
    #                       "_section_" token                           (FL, OR, CO, NV)
    layout: Literal["ny_article", "tx_hierarchical", "flat_section"] = "ny_article"
    # flat_section only: the slug prefix before a section number, e.g. "ors",
    # "crs", "nrs", "fla._stat." — used to tell section links from containers.
    section_prefix: Optional[str] = None
    # Restrict the crawl to these container slugs (NY: article slugs; TX/CA:
    # cumulative container seeds; flat_section: the containers that directly
    # list sections). None = whole code.
    articles: Optional[list[str]] = None


class FetchSpec(BaseModel):
    """An explicit, single-URL source (a form or a practice-rule document).

    Mirrors the fields the existing `apps/ingest` SourceSpec loop needs, so
    these can be fed straight through `_fetch_one` without a parallel path.
    """

    slug: str
    url: str
    kind: Literal["html", "pdf"] = "pdf"
    metadata: dict[str, str] = {}


class StateConfig(BaseModel):
    """Everything needed to build one state's knowledge base."""

    slug: str
    name: str
    public_law_subdomain: str = ""
    # Where statutes come from. "public_law" crawls <subdomain>.public.law;
    # "official" runs a bespoke crawler against the state's own legislature
    # site (states not on public.law — each official site is unique, so each
    # gets its own `apps/ingest/src/official_<slug>.py`).
    fetcher: Literal["public_law", "official"] = "public_law"
    # For fetcher="official": names the bespoke handler (see _OFFICIAL_CRAWLERS
    # in apps/ingest/main.py). "ct_bespoke" delegates to fetch-public.
    official_handler: Optional[str] = None
    statutes: list[StatuteCode] = []
    forms: list[FetchSpec] = []
    practice_rules: list[FetchSpec] = []
    courtlistener_courts: list[str] = []


class JurisdictionsConfig(BaseModel):
    """The whole `config/states.yaml` document, keyed by slug."""

    states: dict[str, StateConfig]


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _states_path() -> Path:
    """Locate the states YAML.

    Honors `LAWAGENT_STATES_FILE`; otherwise `config/states.yaml` at the
    repo root (three levels above this `packages/corpus/` file).
    """
    override = get_settings().states_file
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "config" / "states.yaml"


@lru_cache(maxsize=1)
def load_states() -> JurisdictionsConfig:
    """Load and validate `config/states.yaml` (cached)."""
    path = _states_path()
    if not path.exists():
        raise FileNotFoundError(
            f"States registry not found: {path}. "
            "Expected config/states.yaml at the repo root."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # The YAML keys each state by its slug; mirror that key into the entry so
    # `slug` need not be repeated inside every block.
    for key, entry in (data.get("states") or {}).items():
        if isinstance(entry, dict):
            entry.setdefault("slug", key)
    return JurisdictionsConfig.model_validate(data)


def get_state(state: str) -> StateConfig:
    """Resolve a slug or display name to its `StateConfig`."""
    cfg = load_states()
    key = _slug(state)
    if key in cfg.states:
        return cfg.states[key]
    for entry in cfg.states.values():
        if _slug(entry.name) == key or _slug(entry.slug) == key:
            return entry
    available = ", ".join(sorted(cfg.states)) or "(none)"
    raise ValueError(
        f"Unknown state {state!r}. Defined in config/states.yaml: {available}."
    )


def available_states() -> list[str]:
    """Slugs of every state defined in the registry."""
    return sorted(load_states().states)
