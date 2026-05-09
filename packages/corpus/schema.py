from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    STATUTE = "statute"          # CGS sections, e.g. 46b-82
    PRACTICE_BOOK = "practice_book"  # CT Practice Book rules
    CASE = "case"                # CT appellate decisions
    CASE_FILE = "case_file"      # the author's own case documents


class DocumentMetadata(BaseModel):
    source_type: SourceType
    citation: str = Field(
        description="Canonical citation string, e.g. 'Conn. Gen. Stat. § 46b-82(a)' "
        "or 'Smith v. Smith, 333 Conn. 1 (2019)'."
    )
    title: Optional[str] = None
    section: Optional[str] = None       # e.g. "46b-82"
    subsection: Optional[str] = None    # e.g. "(a)(2)"
    date: Optional[str] = None          # ISO date for cases / Practice Book versions
    source_path: Optional[str] = None   # local file the chunk came from


class Chunk(BaseModel):
    """A retrievable unit of text with the metadata needed to cite it."""

    id: str
    text: str
    metadata: DocumentMetadata
    chunk_index: int = 0

    def to_chroma_metadata(self) -> dict:
        """Flatten to primitive types Chroma will accept."""
        m = self.metadata
        return {
            "source_type": m.source_type.value,
            "citation": m.citation,
            "title": m.title or "",
            "section": m.section or "",
            "subsection": m.subsection or "",
            "date": m.date or "",
            "source_path": m.source_path or "",
            "chunk_index": self.chunk_index,
        }


class Citation(BaseModel):
    """A citation the agent attaches to a claim, traceable to a Chunk."""

    chunk_id: str
    citation: str
    quote: Optional[str] = Field(
        default=None,
        description="Verbatim quote from the chunk supporting the claim.",
    )
