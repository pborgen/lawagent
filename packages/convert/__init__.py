"""Document format conversion.

Pure, side-effect-free converters: bytes in, bytes out. No S3, no FastAPI,
no filesystem layout assumptions — so this stays trivially testable and
reusable from the API, the CLI, or a future batch job.

The only converter so far is PDF -> Word (.docx), used by the file
service so a user can edit an uploaded PDF in Word / Google Docs.
"""
from __future__ import annotations

from .pdf_docx import ConversionError, pdf_to_docx

__all__ = ["pdf_to_docx", "ConversionError"]
