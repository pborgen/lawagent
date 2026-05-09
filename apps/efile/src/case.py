"""Parse the CT eServices case-detail page into structured data.

Produces:
    CaseDetail {
        crn: str
        case_caption: Optional[str]
        court_location: Optional[str]
        case_type: Optional[str]
        filed_date: Optional[str]
        parties: list[Party]
        docket_entries: list[DocketEntry]
        raw_html: str        # snapshotted for diffing later
    }

The selectors below are TODO placeholders. Open the case page in
dev-tools, find the table/section that holds each piece of data, and
fill in the real selectors. The code is shaped so that filling in
the selectors should be a one-place change per field.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from efile.src.throttle import polite_wait


CASE_URL_TEMPLATE = (
    "https://efile.eservices.jud.ct.gov/CaseDetail/AttyCaseDetail.aspx?CRN={crn}"
)


@dataclass
class DocumentLink:
    label: str
    href: str          # absolute URL to the PDF / document handler
    docket_entry_id: Optional[str] = None


@dataclass
class DocketEntry:
    entry_id: str                 # e.g. "101.00" — court's own numbering
    date: Optional[str] = None
    type_: Optional[str] = None   # "Motion", "Order", "Notice", etc.
    description: Optional[str] = None
    documents: list[DocumentLink] = field(default_factory=list)


@dataclass
class Party:
    role: str                     # "Plaintiff", "Defendant", "Counsel", etc.
    name: str


@dataclass
class CaseDetail:
    crn: str
    raw_html: str
    case_caption: Optional[str] = None
    court_location: Optional[str] = None
    case_type: Optional[str] = None
    filed_date: Optional[str] = None
    parties: list[Party] = field(default_factory=list)
    docket_entries: list[DocketEntry] = field(default_factory=list)


def fetch_case_detail(page: Page, crn: str) -> CaseDetail:
    """Navigate to the case page (with polite wait) and parse it."""
    url = CASE_URL_TEMPLATE.format(crn=crn)
    page.goto(url, wait_until="networkidle")
    polite_wait("after case detail load")

    html = page.content()
    return parse_case_detail(crn, html, base_url=url)


def parse_case_detail(crn: str, html: str, *, base_url: str) -> CaseDetail:
    soup = BeautifulSoup(html, "html.parser")
    detail = CaseDetail(crn=crn, raw_html=html)

    # ─── TODO: case header (caption, court, type, filed date) ────────
    # Open dev-tools on the case page, find the elements, fill in.
    # Example:
    #   detail.case_caption = _text(soup.select_one("#caseCaption"))
    #   detail.court_location = _text(soup.select_one("#caseCourt"))
    # ────────────────────────────────────────────────────────────────

    # ─── TODO: parties ───────────────────────────────────────────────
    # Typical pattern: a table with rows of role + name.
    #   for tr in soup.select("table.parties tr"):
    #       tds = tr.select("td")
    #       if len(tds) >= 2:
    #           detail.parties.append(
    #               Party(role=_text(tds[0]) or "?", name=_text(tds[1]) or "")
    #           )
    # ────────────────────────────────────────────────────────────────

    # ─── TODO: docket entries ────────────────────────────────────────
    # The docket is the part you most care about. Each row usually has:
    #   entry_id | date | type | description | [doc links]
    # Example skeleton — adjust selectors:
    #   for tr in soup.select("table.docket tbody tr"):
    #       tds = tr.select("td")
    #       if len(tds) < 4:
    #           continue
    #       entry = DocketEntry(
    #           entry_id=_text(tds[0]) or "",
    #           date=_text(tds[1]),
    #           type_=_text(tds[2]),
    #           description=_text(tds[3]),
    #       )
    #       for a in tr.select("a[href]"):
    #           href = a.get("href") or ""
    #           if not href:
    #               continue
    #           if href.startswith("/"):
    #               href = _absolute(base_url, href)
    #           entry.documents.append(
    #               DocumentLink(
    #                   label=_text(a) or "document",
    #                   href=href,
    #                   docket_entry_id=entry.entry_id,
    #               )
    #           )
    #       detail.docket_entries.append(entry)
    # ────────────────────────────────────────────────────────────────

    return detail


def _text(el) -> Optional[str]:
    if el is None:
        return None
    s = el.get_text(strip=True)
    return s or None


def _absolute(base_url: str, href: str) -> str:
    """Resolve a relative href against the case-detail page URL."""
    from urllib.parse import urljoin

    return urljoin(base_url, href)
