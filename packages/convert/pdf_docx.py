"""PDF -> Word (.docx) conversion.

Built on `pdf2docx`, which itself runs on PyMuPDF (already a project
dependency). pdf2docx preserves text and tables for *digital* PDFs.

Scanned / image-only PDFs have no text layer: pdf2docx will embed the
page images into the .docx, so the result opens in Word but isn't
editable text. We detect that case and report it via the `had_text`
return value so callers can warn the user. OCR-to-editable is a
deliberate follow-up, not handled here.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import fitz  # PyMuPDF

# pdf2docx is noisy at INFO; callers can quiet it via logging config.
from pdf2docx import Converter

# A PDF with essentially no extractable text is treated as scanned. A few
# stray characters (page numbers from a scanner's header) shouldn't flip
# the verdict, so we use a small threshold rather than `> 0`.
_TEXT_LAYER_MIN_CHARS = 20


class ConversionError(Exception):
    """Raised when a PDF cannot be converted to .docx."""


def _has_text_layer(pdf_bytes: bytes) -> bool:
    """True if the PDF carries an extractable text layer (i.e. not scanned)."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            total = sum(len(page.get_text().strip()) for page in doc)
    except Exception as exc:  # malformed / not a PDF
        raise ConversionError(f"Not a readable PDF: {exc}") from exc
    return total >= _TEXT_LAYER_MIN_CHARS


def pdf_to_docx(pdf_bytes: bytes) -> tuple[bytes, bool]:
    """Convert a PDF to a Word .docx.

    Returns ``(docx_bytes, had_text)``. ``had_text`` is False for scanned /
    image-only PDFs, whose .docx will contain page images rather than
    editable text.

    Raises ``ConversionError`` if the bytes aren't a usable PDF or pdf2docx
    fails on them.
    """
    had_text = _has_text_layer(pdf_bytes)

    # pdf2docx is path-oriented, so round-trip through a temp dir.
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.pdf"
        dst = Path(tmp) / "out.docx"
        src.write_bytes(pdf_bytes)
        try:
            cv = Converter(str(src))
            try:
                cv.convert(str(dst))
            finally:
                cv.close()
        except Exception as exc:
            raise ConversionError(f"PDF -> DOCX conversion failed: {exc}") from exc

        if not dst.exists():
            raise ConversionError("Conversion produced no output.")
        return dst.read_bytes(), had_text
