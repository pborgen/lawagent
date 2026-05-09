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

from playwright.sync_api import BrowserContext
from rich.console import Console

from efile.src.case import CaseDetail, DocumentLink
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
    """Map href → downloaded_path from the prior manifest, for idempotency."""
    out: dict[str, str] = {}
    for entry in prev.get("docket_entries", []):
        for doc in entry.get("documents", []):
            href = doc.get("href")
            path = doc.get("downloaded_path")
            if href and path:
                out[href] = path
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

    for entry in detail.docket_entries:
        for doc in entry.documents:
            existing = already_have.get(doc.href)
            if existing and (base / existing).exists():
                # Already downloaded.
                doc_dict = _doc_to_dict(doc, existing, _sha256(base / existing))
                _attach(doc, doc_dict)
                skipped_count += 1
                continue

            polite_wait("before document download")
            download_delay()
            rel_path = with_retry(
                lambda d=doc, e=entry: _download_one(context, d, e, docs_dir, base),
                attempts=3,
                base_backoff=10.0,
                label=f"download {doc.label}",
            )
            sha = _sha256(base / rel_path)
            doc_dict = _doc_to_dict(doc, rel_path, sha)
            _attach(doc, doc_dict)
            new_count += 1

    manifest = _serialize_case(detail)
    manifest["last_pulled_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest["counts"] = {
        "new_downloads": new_count,
        "skipped_already_present": skipped_count,
        "total_docket_entries": len(detail.docket_entries),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _attach(doc: DocumentLink, doc_dict: dict) -> None:
    """Stash the result on the dataclass so _serialize_case picks it up via asdict."""
    # asdict() only serializes declared fields, so we set them on the instance:
    setattr(doc, "downloaded_path", doc_dict["downloaded_path"])
    setattr(doc, "sha256", doc_dict["sha256"])


def _doc_to_dict(doc: DocumentLink, rel_path: str, sha: str) -> dict:
    return {
        "label": doc.label,
        "href": doc.href,
        "docket_entry_id": doc.docket_entry_id,
        "downloaded_path": rel_path,
        "sha256": sha,
    }


def _download_one(
    context: BrowserContext,
    doc: DocumentLink,
    entry,
    docs_dir: Path,
    base_dir: Path,
) -> str:
    """Fetch the document via the context's API request (shares session cookies)
    and save it. Return the path relative to `base_dir`.

    We use context.request rather than driving a browser page because CT serves
    docs as direct attachment responses. expect_download() on a new page is
    flaky for that flow (the download event sometimes never fires); a plain
    HTTP GET with the same cookies is deterministic.
    """
    console.print(f"Downloading [bold]{doc.label}[/bold] (entry {entry.entry_id}) from {doc.href}")
    response = context.request.get(doc.href)
    try:
        if not response.ok:
            raise RuntimeError(
                f"HTTP {response.status} {response.status_text} fetching {doc.href}"
            )
        body = response.body()
    finally:
        response.dispose()

    # Borrow extension from server's filename hint when present.
    cd = response.headers.get("content-disposition", "") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\'|")?([^";]+)', cd)
    suggested = (m.group(1).strip('"') if m else "")
    ext = Path(suggested).suffix or ".pdf"

    prefix = f"{entry.entry_id}__" if entry.entry_id else ""
    filename = f"{prefix}{_safe_filename(doc.label)}{ext}"
    target = docs_dir / filename
    target.write_bytes(body)
    return str(target.relative_to(base_dir))
