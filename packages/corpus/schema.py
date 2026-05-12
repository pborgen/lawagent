from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    STATUTE = "statute"  # CGS sections, e.g. 46b-82
    PRACTICE_BOOK = "practice_book"  # CT Practice Book rules
    CASE = "case"  # CT appellate decisions
    COURT_FORM = "court_form"  # CT Judicial Branch forms
    COURT_GUIDE = "court_guide"  # CT Judicial Branch public guidance
    LAW_LIBRARY_GUIDE = "law_library_guide"  # CT Judicial Branch research guides
    CASE_FILE = "case_file"  # the author's own case documents


class AuthorityLevel(str, Enum):
    PRIMARY = "primary"
    COURT_RULE = "court_rule"
    COURT_PUBLISHED = "court_published"
    SECONDARY = "secondary"
    PERSONAL = "personal"


class DocumentMetadata(BaseModel):
    source_type: SourceType
    authority_level: AuthorityLevel
    citation: str = Field(
        description="Canonical citation string, e.g. 'Conn. Gen. Stat. § 46b-82(a)' "
        "or 'Smith v. Smith, 333 Conn. 1 (2019)'."
    )
    title: Optional[str] = None
    section: Optional[str] = None  # e.g. "46b-82"
    subsection: Optional[str] = None  # e.g. "(a)(2)"
    date: Optional[str] = None  # ISO date for cases / Practice Book versions
    jurisdiction: Optional[str] = None  # e.g. "Connecticut"
    issuing_body: Optional[str] = None  # e.g. "Connecticut Judicial Branch"
    topic: Optional[str] = None  # e.g. "alimony" or "custody"
    stage: Optional[str] = None  # e.g. "pre-filing", "temporary-orders"
    document_id: Optional[str] = None  # e.g. "JD-FM-159"
    source_url: Optional[str] = None  # official upstream URL
    source_path: Optional[str] = None  # local file the chunk came from


class Chunk(BaseModel):
    """A retrievable unit of text with the metadata needed to cite it."""

    id: str
    text: str
    metadata: DocumentMetadata
    chunk_index: int = 0

    def to_metadata_dict(self) -> dict:
        """Flatten to a primitive dict the vector store can store as JSONB."""
        m = self.metadata
        return {
            "source_type": m.source_type.value,
            "authority_level": m.authority_level.value,
            "citation": m.citation,
            "title": m.title or "",
            "section": m.section or "",
            "subsection": m.subsection or "",
            "date": m.date or "",
            "jurisdiction": m.jurisdiction or "",
            "issuing_body": m.issuing_body or "",
            "topic": m.topic or "",
            "stage": m.stage or "",
            "document_id": m.document_id or "",
            "source_url": m.source_url or "",
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
