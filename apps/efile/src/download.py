"""Download docket-entry documents and maintain a manifest.

Idempotent: re-runs skip files already on disk whose URL is recorded
in the manifest. Throttled: every download is preceded by a polite wait.

Manifest layout (JSON, written to data/case/efile/<crn>/manifest.json):

{
  "crn": "5124226",
  "last_pulled_at": "2026-05-09T15:32:11Z",
  "case_caption": "...",
  ...
  "docket_entries": [
    {
      "entry_id": "101.00",
      "date": "2026-04-15",
      "type": "Motion",
      "description": "...",
      "documents": [
        {
          "label": "Motion for Pendente Lite Alimony",
          "href": "https://...",
          "downloaded_path": "docs/101.00__motion-for-pendente-lite.pdf",
          "sha256": "..."
        }
      ]
    }
  ]
}
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import BrowserContext
from rich.console import Console

from efile.src.case import CaseDetail, DocumentAttachment, DocumentLink
from efile.src.throttle import download_delay, polite_wait, with_retry

console = Console()


def case_dir(crn: str) -> Path:
    return Path("data/case/efile") / crn


def _safe_filename(label: str) -> str:
    s = re.sub(r"[^\w\-. ]+", "_", label).strip().strip(".")
    return s[:120] or "document"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _previous_downloads(prev: dict) -> dict[str, str]:
    """Map href → downloaded_path from the prior manifest, for idempotency.

    Includes both main-doc hrefs and any DocumentInquiry attachments
    (exhibits) discovered on a previous run.
    """
    out: dict[str, str] = {}
    for entry in prev.get("docket_entries", []):
        for doc in entry.get("documents", []):
            href = doc.get("href")
            path = doc.get("downloaded_path")
            if href and path:
                out[href] = path
            for att in doc.get("attachments", []) or []:
                att_href = att.get("href")
                att_path = att.get("downloaded_path")
                if att_href and att_path:
                    out[att_href] = att_path
    return out


def _serialize_case(detail: CaseDetail) -> dict:
    """Produce the JSON-shaped dict for the manifest, minus raw_html."""
    d = asdict(detail)
    d.pop("raw_html", None)
    return d


def download_documents(
    context: BrowserContext,
    detail: CaseDetail,
    *,
    out_dir: Optional[Path] = None,
) -> dict:
    """Download all documents in the case docket, return the new manifest dict."""
    base = out_dir or case_dir(detail.crn)
    docs_dir = base / "docs"
    pages_dir = base / "pages"
    docs_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot the raw page HTML for diffing later.
    (pages_dir / "case.html").write_text(detail.raw_html, encoding="utf-8")

    manifest_path = base / "manifest.json"
    prev_manifest = _load_manifest(manifest_path)
    already_have = _previous_downloads(prev_manifest)

    new_count = 0
    skipped_count = 0
    attachment_new_count = 0
    attachment_skipped_count = 0

    for entry in detail.docket_entries:
        for doc in entry.documents:
            # Main document.
            existing = already_have.get(doc.href)
            if existing and (base / existing).exists():
                _attach_main(doc, existing, _sha256(base / existing))
                skipped_count += 1
            else:
                polite_wait("before document download")
                download_delay()
                main_path, attachment_links = with_retry(
                    lambda d=doc, e=entry: _download_one(
                        context, d, e, docs_dir, base
                    ),
                    attempts=3,
                    base_backoff=10.0,
                    label=f"download {doc.label}",
                )
                _attach_main(doc, main_path, _sha256(base / main_path))
                new_count += 1
                # Persist discovered attachment URLs onto the doc so the loop
                # below downloads them (and so they re-key idempotency on the
                # next pull).
                for att in attachment_links:
                    doc.attachments.append(att)

            # Attachments (exhibits) discovered from a DocumentInquiry HTML
            # landing page — may be empty for direct-PDF responses.
            for att in doc.attachments:
                att_existing = already_have.get(att.href)
                if att_existing and (base / att_existing).exists():
                    att.downloaded_path = att_existing
                    att.sha256 = _sha256(base / att_existing)
                    attachment_skipped_count += 1
                    continue
                polite_wait("before attachment download")
                download_delay()
                att_rel_path = with_retry(
                    lambda a=att, e=entry: _download_attachment(
                        context, a, e, docs_dir, base
                    ),
                    attempts=3,
                    base_backoff=10.0,
                    label=f"download attachment {att.label}",
                )
                att.downloaded_path = att_rel_path
                att.sha256 = _sha256(base / att_rel_path)
                attachment_new_count += 1

    manifest = _serialize_case(detail)
    manifest["last_pulled_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest["counts"] = {
        "new_downloads": new_count,
        "skipped_already_present": skipped_count,
        "new_attachments": attachment_new_count,
        "skipped_attachments": attachment_skipped_count,
        "total_docket_entries": len(detail.docket_entries),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _attach_main(doc: DocumentLink, rel_path: str, sha: str) -> None:
    """Stash the result on the dataclass so _serialize_case picks it up via asdict."""
    doc.downloaded_path = rel_path
    doc.sha256 = sha


def _download_one(
    context: BrowserContext,
    doc: DocumentLink,
    entry,
    docs_dir: Path,
    base_dir: Path,
) -> tuple[str, list[DocumentAttachment]]:
    """Fetch the main filing PDF and (if applicable) discover its exhibits.

    CT eServices returns one of two shapes at a DocumentInquiry URL:
      1. The PDF directly (application/pdf) — the common case, save and done.
      2. An HTML landing page that links to the main PDF plus N attached
         exhibits/affidavits — we save the main PDF and return the exhibit
         links so the caller can pull each.

    Returns (main_rel_path, attachments). `attachments` is empty for shape (1).

    We use context.request rather than driving a browser page because CT serves
    docs as direct attachment responses. expect_download() on a new page is
    flaky for that flow (the download event sometimes never fires); a plain
    HTTP GET with the same cookies is deterministic.
    """
    console.print(f"Downloading [bold]{doc.label}[/bold] (entry {entry.entry_id}) from {doc.href}")
    body, content_type, cd_header, final_url = _request_bytes(context, doc.href)

    prefix = f"{entry.entry_id}__" if entry.entry_id else ""

    # Sealed-document interstitial (PB § 25-59A(h)): GET returns an HTML
    # page with a "Proceed" button instead of the document. Re-POST the
    # form with btnSAProceed=Proceed and use that response instead.
    if not _looks_like_pdf(body, content_type, cd_header):
        bypassed = _bypass_sealed_interstitial(
            context,
            url=final_url or doc.href,
            html=body.decode("utf-8", errors="replace"),
        )
        if bypassed is not None:
            body, content_type, cd_header, final_url = bypassed

    if _looks_like_pdf(body, content_type, cd_header):
        ext = _suggested_ext(cd_header) or ".pdf"
        filename = f"{prefix}{_safe_filename(doc.label)}{ext}"
        target = docs_dir / filename
        target.write_bytes(body)
        return str(target.relative_to(base_dir)), []

    # HTML landing page — parse it for the main PDF and any exhibits.
    inquiry_html = body.decode("utf-8", errors="replace")
    links = _parse_inquiry_links(inquiry_html, base_url=final_url or doc.href)
    if not links:
        # Save the unexpected HTML for inspection so we can tune the parser.
        debug_dir = base_dir.parent / "_debug" / "inquiry"
        debug_dir.mkdir(parents=True, exist_ok=True)
        snapshot = debug_dir / f"{prefix}{_safe_filename(doc.label)}.html"
        snapshot.write_text(inquiry_html, encoding="utf-8")
        raise RuntimeError(
            f"DocumentInquiry returned HTML with no parseable PDF links for "
            f"{doc.href} (entry {entry.entry_id}). Snapshot: {snapshot}. "
            "Tune _parse_inquiry_links() against the saved HTML."
        )

    # Convention: the first link is the main filing; the rest are exhibits.
    main_link = links[0]
    main_body, main_ct, main_cd, _ = _request_bytes(context, main_link.href)
    if not _looks_like_pdf(main_body, main_ct, main_cd):
        raise RuntimeError(
            f"Expected PDF at {main_link.href} but got content-type={main_ct!r}"
        )
    ext = _suggested_ext(main_cd) or ".pdf"
    main_filename = f"{prefix}{_safe_filename(doc.label)}{ext}"
    (docs_dir / main_filename).write_bytes(main_body)
    main_rel = str((docs_dir / main_filename).relative_to(base_dir))

    attachments = [
        DocumentAttachment(label=link.label, href=link.href) for link in links[1:]
    ]
    if attachments:
        console.print(
            f"  Found [bold]{len(attachments)}[/bold] exhibit(s) on inquiry page "
            f"for entry {entry.entry_id}"
        )
    return main_rel, attachments


def _download_attachment(
    context: BrowserContext,
    att: DocumentAttachment,
    entry,
    docs_dir: Path,
    base_dir: Path,
) -> str:
    """Download one exhibit/attachment discovered on a DocumentInquiry page."""
    console.print(
        f"  Downloading exhibit [bold]{att.label}[/bold] "
        f"(entry {entry.entry_id}) from {att.href}"
    )
    body, content_type, cd_header, _ = _request_bytes(context, att.href)
    if not _looks_like_pdf(body, content_type, cd_header):
        raise RuntimeError(
            f"Expected PDF for exhibit {att.label} at {att.href} but got "
            f"content-type={content_type!r}"
        )
    ext = _suggested_ext(cd_header) or ".pdf"
    prefix = f"{entry.entry_id}__" if entry.entry_id else ""
    filename = f"{prefix}exhibit__{_safe_filename(att.label)}{ext}"
    target = docs_dir / filename
    target.write_bytes(body)
    return str(target.relative_to(base_dir))


_SEALED_INTERSTITIAL_MARKERS = ("pnlSealedAffQuestion", "btnSAProceed")


def _bypass_sealed_interstitial(
    context: BrowserContext, *, url: str, html: str
) -> Optional[tuple[bytes, str, str, Optional[str]]]:
    """Bypass the 'sealed pursuant to PB § 25-59A(h)' acknowledgement page.

    Some DocumentInquiry URLs return an HTML interstitial with a Proceed
    button before serving the actual document — common for sealed family
    matters filings (financial affidavits, etc.) where the requesting
    party still has access. ASP.NET requires a POST of the original form
    (with all __VIEWSTATE / __EVENTVALIDATION hidden fields plus
    btnSAProceed=Proceed) to acknowledge the warning and get the doc.

    Returns the post-bypass response tuple, or None if `html` is not an
    interstitial we recognize.
    """
    if not any(marker in html for marker in _SEALED_INTERSTITIAL_MARKERS):
        return None

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form is None:
        return None

    form_data: dict[str, str] = {}
    for inp in form.find_all("input"):
        if (inp.get("type") or "").lower() == "hidden":
            name = inp.get("name")
            if name:
                form_data[name] = inp.get("value", "") or ""
    form_data["btnSAProceed"] = "Proceed"

    action = (form.get("action") or "").strip() or url
    target = urljoin(url, action)

    console.print("  [yellow]Sealed-document interstitial — clicking Proceed[/yellow]")
    response = context.request.post(target, form=form_data)
    try:
        if not response.ok:
            raise RuntimeError(
                f"Sealed-doc bypass POST failed: HTTP {response.status} "
                f"{response.status_text} for {target}"
            )
        body = response.body()
        headers = response.headers
        final_url = response.url
    finally:
        response.dispose()
    return (
        body,
        (headers.get("content-type", "") or "").lower(),
        headers.get("content-disposition", "") or "",
        final_url,
    )


def _request_bytes(
    context: BrowserContext, url: str
) -> tuple[bytes, str, str, Optional[str]]:
    """GET a URL with the browser context's cookies. Returns (body, content_type, content_disposition, final_url)."""
    response = context.request.get(url)
    try:
        if not response.ok:
            raise RuntimeError(
                f"HTTP {response.status} {response.status_text} fetching {url}"
            )
        body = response.body()
        headers = response.headers
        final_url = response.url
    finally:
        response.dispose()
    return (
        body,
        (headers.get("content-type", "") or "").lower(),
        headers.get("content-disposition", "") or "",
        final_url,
    )


def _looks_like_pdf(body: bytes, content_type: str, cd_header: str) -> bool:
    if body.startswith(b"%PDF"):
        return True
    if "application/pdf" in content_type:
        return True
    if ".pdf" in cd_header.lower():
        return True
    return False


def _suggested_ext(cd_header: str) -> Optional[str]:
    """Pull a file extension from a Content-Disposition filename hint, if any."""
    if not cd_header:
        return None
    m = re.search(r'filename\*?=(?:UTF-8\'\'|")?([^";]+)', cd_header)
    if not m:
        return None
    suggested = m.group(1).strip('"')
    return Path(suggested).suffix or None


class _InquiryLink:
    def __init__(self, label: str, href: str) -> None:
        self.label = label
        self.href = href


def _parse_inquiry_links(html: str, *, base_url: str) -> list[_InquiryLink]:
    """Extract document links from a CT eServices DocumentInquiry HTML page.

    The page format is server-rendered ASP.NET and the exact selectors aren't
    fully documented. We look broadly: any anchor whose href points at a file
    download (PDF / Office / image) or at a known CT eServices document
    endpoint. Order is preserved — the caller treats the first link as the
    main filing and the rest as exhibits.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[_InquiryLink] = []
    seen: set[str] = set()

    DOCUMENT_PATH_HINTS = (
        "/documentinquiry/",
        "/pdfgenerator",
        "/getdocument",
        "/viewdocument",
        "/download",
    )
    DOCUMENT_EXT_HINTS = (".pdf", ".doc", ".docx", ".tif", ".tiff", ".jpg", ".jpeg", ".png")

    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        abs_href = urljoin(base_url, href)
        low = abs_href.lower()
        looks_like_doc = (
            any(low.endswith(ext) for ext in DOCUMENT_EXT_HINTS)
            or any(hint in low for hint in DOCUMENT_PATH_HINTS)
        )
        if not looks_like_doc:
            continue
        if abs_href in seen:
            continue
        seen.add(abs_href)
        label = (a.get_text(" ", strip=True) or a.get("title") or "document")[:120]
        out.append(_InquiryLink(label=label, href=abs_href))

    return out
