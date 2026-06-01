"""Unit tests for packages/convert (PDF -> Word).

Uses PyMuPDF (a core dependency) to synthesize tiny PDFs in memory, so
these run anywhere `make check` runs — no fixtures, no network, no DB.
"""
from __future__ import annotations

import io
import zipfile

import fitz  # PyMuPDF
import pytest

from convert import ConversionError, pdf_to_docx


def _pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _blank_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()  # no text drawn
    data = doc.tobytes()
    doc.close()
    return data


def _is_docx(data: bytes) -> bool:
    """A .docx is a zip (PK magic) containing word/document.xml."""
    if data[:2] != b"PK":
        return False
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return "word/document.xml" in zf.namelist()


def test_digital_pdf_converts_with_text_layer():
    docx, had_text = pdf_to_docx(_pdf_with_text("Motion to modify alimony."))
    assert _is_docx(docx)
    assert had_text is True


def test_scanned_like_pdf_reports_no_text_layer():
    # A page with no extractable text stands in for a scanned image.
    docx, had_text = pdf_to_docx(_blank_pdf())
    assert _is_docx(docx)
    assert had_text is False


def test_non_pdf_bytes_raise_conversion_error():
    with pytest.raises(ConversionError):
        pdf_to_docx(b"this is not a pdf")
