"""Convert a PDF to per-page text + a markdown rendering.

Strategy: try PyMuPDF's native text extraction first (fast, works for any
e-filed / digitally-generated PDF). If a page yields fewer than
MIN_NATIVE_CHARS of text, render it to a pixmap and OCR it with Tesseract.
Court dockets mix both kinds — newer e-files are digital, older scanned-in
exhibits aren't — so the per-page fallback handles both without forcing
OCR on everything.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image


# A page with fewer than this many characters of native text is treated as
# scanned and routed through OCR. 30 is conservative — most digital pages
# have hundreds; mostly-blank pages of digital docs (signature pages) will
# still pass through native extraction with a few words.
MIN_NATIVE_CHARS = 30
OCR_DPI = 300


@dataclass
class PageResult:
    page: int
    text: str
    ocr_used: bool


@dataclass
class DocResult:
    source_pdf: Path
    source_sha256: str
    page_count: int
    ocr_used: bool
    pages: list[PageResult] = field(default_factory=list)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_pdf(pdf_path: Path) -> DocResult:
    doc = fitz.open(pdf_path)
    try:
        pages: list[PageResult] = []
        for i, page in enumerate(doc, start=1):
            native = (page.get_text() or "").strip()
            if len(native) >= MIN_NATIVE_CHARS:
                pages.append(PageResult(page=i, text=native, ocr_used=False))
                continue

            pix = page.get_pixmap(dpi=OCR_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img).strip()
            pages.append(PageResult(page=i, text=ocr_text, ocr_used=True))

        return DocResult(
            source_pdf=pdf_path,
            source_sha256=sha256(pdf_path),
            page_count=len(pages),
            ocr_used=any(p.ocr_used for p in pages),
            pages=pages,
        )
    finally:
        doc.close()


def to_markdown(result: DocResult) -> str:
    parts = [f"# {result.source_pdf.name}", ""]
    for p in result.pages:
        suffix = " (OCR)" if p.ocr_used else ""
        parts.append(f"## Page {p.page}{suffix}")
        parts.append("")
        parts.append(p.text or "_(no text extracted)_")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def to_sidecar(result: DocResult, source_rel: str) -> dict:
    return {
        "source_pdf": source_rel,
        "source_sha256": result.source_sha256,
        "page_count": result.page_count,
        "ocr_used": result.ocr_used,
        "converted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pages": [
            {"page": p.page, "text": p.text, "ocr_used": p.ocr_used}
            for p in result.pages
        ],
    }
