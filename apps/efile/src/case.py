"""Parse the CT eServices case-detail page into structured data.

Produces:
    CaseDetail {
        crn: str
        docket_no: Optional[str]     # e.g. "HHD-FA25-5089318-S"
        case_caption: Optional[str]
        court_location: Optional[str]
        case_type: Optional[str]
        filed_date: Optional[str]
        return_date: Optional[str]
        parties: list[Party]
        docket_entries: list[DocketEntry]
        raw_html: str                # snapshotted for diffing later
    }

The CT eServices server requires a "priming" step before AttyCaseDetail.aspx
will render data — visiting LoadDocket.aspx?DocketNo=... first sets per-case
session state, then AttyCaseDetail.aspx?CRN=... shows real values. We don't
have the docket no up front, so `fetch_case_detail` walks AttyCaseHistory
first and clicks the matching case link.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from efile.src.throttle import polite_wait


CASE_HISTORY_URL = "https://efile.eservices.jud.ct.gov/CaseDetail/AttyCaseHistory.aspx"


@dataclass
class DocumentLink:
    label: str
    href: str          # absolute URL to the DocumentInquiry page (where the PDF lives)
    docket_entry_id: Optional[str] = None
    downloaded_path: Optional[str] = None  # populated post-download (relative to case dir)
    sha256: Optional[str] = None           # populated post-download


@dataclass
class DocketEntry:
    order: int                    # 1-indexed position in the docket as the court displays it
    entry_id: str                 # CT eServices "Entry No" — often blank; we fall back to the DocumentNo from the link
    date: Optional[str] = None    # File Date, e.g. "06/25/2025"
    filed_by: Optional[str] = None   # P / D / Court / etc.
    description: Optional[str] = None  # document name (e.g. "SUMMONS") + any add-desc / notes
    documents: list[DocumentLink] = field(default_factory=list)


@dataclass
class Party:
    role: str                     # raw party id, e.g. "P-01" / "D-01"
    name: str


@dataclass
class CaseDetail:
    crn: str
    raw_html: str
    docket_no: Optional[str] = None
    case_caption: Optional[str] = None
    court_location: Optional[str] = None
    case_type: Optional[str] = None
    filed_date: Optional[str] = None
    return_date: Optional[str] = None
    parties: list[Party] = field(default_factory=list)
    docket_entries: list[DocketEntry] = field(default_factory=list)


def fetch_case_detail(page: Page, crn: str) -> CaseDetail:
    """Prime the case session via AttyCaseHistory, then parse the resulting detail page.

    AttyCaseDetail.aspx?CRN=... returns empty fields when hit cold; clicking
    the docket-no link in case history routes through LoadDocket.aspx (which
    sets server-side state) and lands on AttyCaseDetail with real data.
    """
    page.goto(CASE_HISTORY_URL, wait_until="networkidle")
    polite_wait("after case history load")

    docket_link = page.locator("a[id*='hlnkDocketNo'][href*='LoadDocket']").first
    if docket_link.count() == 0:
        raise RuntimeError(
            "No case docket link found on AttyCaseHistory.aspx. Are you logged in "
            "as the right user, and does this account have access to a case?"
        )

    docket_link.click()
    page.wait_for_load_state("networkidle")
    polite_wait("after case detail load")

    html = page.content()
    return parse_case_detail(crn, html, base_url=page.url)


# ─── ASP.NET id prefixes on the case detail page ─────────────────────
_HEADER = "Master1_ContentPlaceHolder1_CaseDetailHeader1_"
_BASIC = "Master1_ContentPlaceHolder1_CaseDetailBasicInfo1_"
_PARTIES_GRID_ID = "Master1_ContentPlaceHolder1_CaseDetailParties1_gvParties"
_DOCKET_GRID_ID = "Master1_ContentPlaceHolder1_CaseDetailDocuments1_gvDocuments"


def parse_case_detail(crn: str, html: str, *, base_url: str) -> CaseDetail:
    soup = BeautifulSoup(html, "html.parser")
    detail = CaseDetail(crn=crn, raw_html=html)

    # Header — each span contains "<b>Label:</b> value"; strip the bolded prefix.
    detail.case_caption = _clean(_text(soup.select_one(f"#{_HEADER}lblCaseCaption")))
    detail.docket_no = _strip_label(_text(soup.select_one(f"#{_HEADER}lblDocketNo")))
    detail.case_type = _strip_label(_text(soup.select_one(f"#{_HEADER}lblCaseType")))
    detail.filed_date = _strip_label(_text(soup.select_one(f"#{_HEADER}lblFileDate")))
    detail.return_date = _strip_label(_text(soup.select_one(f"#{_HEADER}lblReturnDate")))

    # Basic info: family-action labels (lblFA*) populate for Family cases;
    # plain lblBasic* are the fallback for civil/other case types.
    detail.court_location = _clean(
        _text(soup.select_one(f"#{_BASIC}lblFABasicLocation"))
        or _text(soup.select_one(f"#{_BASIC}lblBasicLocation"))
    )
    full_case_type = _clean(
        _text(soup.select_one(f"#{_BASIC}lblFABasicCaseType"))
        or _text(soup.select_one(f"#{_BASIC}lblBasicCaseType"))
    )
    if full_case_type:
        # Prefer the descriptive form ("F00 - Family - Dissolution of Marriage…")
        # over the bare code from the header.
        detail.case_type = full_case_type

    # Parties grid — each data row's first cell holds the party id ("P-01"),
    # and the name lives in a nested span ending in "lblPtyPartyName".
    parties_table = soup.select_one(f"#{_PARTIES_GRID_ID}")
    if parties_table:
        for tr in parties_table.select("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2:
                continue
            role = _clean(_text(tds[0]))
            name_span = tds[1].select_one("span[id$='lblPtyPartyName']")
            name = _clean(_text(name_span))
            if role and name:
                detail.parties.append(Party(role=role, name=name))

    # Docket grid — columns: Entry No | File Date | Filed By | Description.
    # Description cell contains the document anchor (id ending in "hlnkDocument")
    # plus optional add-desc / notes / result spans.
    docket_table = soup.select_one(f"#{_DOCKET_GRID_ID}")
    if docket_table:
        for tr in docket_table.select("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 4:
                continue  # header row or malformed
            anchor = tds[3].select_one("a[id$='hlnkDocument']")
            if anchor is None:
                continue  # skip rows without a document link

            href = anchor.get("href") or ""
            abs_href = _absolute(base_url, href) if href else ""
            label = _clean(_text(anchor)) or "document"

            # Pull "additional description" / notes if present, append to description.
            extras = [
                _clean(_text(tds[3].select_one("span[id$='lblAddDesc']"))),
                _clean(_text(tds[3].select_one("span[id$='lblNotes']"))),
                _clean(_text(tds[3].select_one("span[id$='lblResult']"))),
            ]
            description = " — ".join([label, *(e for e in extras if e)])

            entry_id = _clean(_text(tds[0])) or _doc_no_from_href(abs_href) or ""

            entry = DocketEntry(
                order=len(detail.docket_entries) + 1,
                entry_id=entry_id,
                date=_clean(_text(tds[1])),
                filed_by=_clean(_text(tds[2])),
                description=description,
                documents=[
                    DocumentLink(
                        label=label,
                        href=abs_href,
                        docket_entry_id=entry_id or None,
                    )
                ],
            )
            detail.docket_entries.append(entry)

    return detail


def _text(el) -> Optional[str]:
    if el is None:
        return None
    s = el.get_text(strip=True)
    return s or None


def _clean(s: Optional[str]) -> Optional[str]:
    """Collapse whitespace + non-breaking spaces, return None for empties."""
    if s is None:
        return None
    s = s.replace("\xa0", " ").strip()
    s = " ".join(s.split())
    return s or None


def _strip_label(s: Optional[str]) -> Optional[str]:
    """Remove a leading "Label:" prefix (header spans render as "<b>Foo:</b> bar")."""
    s = _clean(s)
    if not s:
        return None
    if ":" in s:
        _, _, rest = s.partition(":")
        return rest.strip() or None
    return s


def _doc_no_from_href(href: str) -> Optional[str]:
    """Extract DocumentNo=... from a DocumentInquiry URL, if present."""
    if not href or "DocumentNo=" not in href:
        return None
    tail = href.split("DocumentNo=", 1)[1]
    return tail.split("&", 1)[0] or None


def _absolute(base_url: str, href: str) -> str:
    from urllib.parse import urljoin

    return urljoin(base_url, href)
