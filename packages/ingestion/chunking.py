from __future__ import annotations

import hashlib
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from corpus import Chunk, DocumentMetadata, SourceType


# Filename conventions used by the ingest pipeline to infer source type / citation:
#
#   cgs-46b-82.txt           → STATUTE, citation "Conn. Gen. Stat. § 46b-82"
#   pb-25-26.txt             → PRACTICE_BOOK, citation "Conn. Practice Book § 25-26"
#   case-smith-v-smith.txt   → CASE, citation derived from first line of the file
#   anything-else.txt        → CASE_FILE (treated as the author's own document)
#
# Override by adding explicit metadata files later if this gets restrictive.

_CGS_RE = re.compile(r"^cgs-([0-9a-z\-]+)$", re.IGNORECASE)
_PB_RE = re.compile(r"^pb-([0-9a-z\-]+)$", re.IGNORECASE)
_CASE_RE = re.compile(r"^case-(.+)$", re.IGNORECASE)


def metadata_from_path(path: Path) -> DocumentMetadata:
    stem = path.stem.lower()

    if m := _CGS_RE.match(stem):
        section = m.group(1)
        return DocumentMetadata(
            source_type=SourceType.STATUTE,
            citation=f"Conn. Gen. Stat. § {section}",
            title=f"CGS § {section}",
            section=section,
            source_path=str(path),
        )

    if m := _PB_RE.match(stem):
        section = m.group(1)
        return DocumentMetadata(
            source_type=SourceType.PRACTICE_BOOK,
            citation=f"Conn. Practice Book § {section}",
            title=f"Practice Book § {section}",
            section=section,
            source_path=str(path),
        )

    if m := _CASE_RE.match(stem):
        slug = m.group(1)
        first_line = ""
        try:
            first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
        except Exception:
            pass
        return DocumentMetadata(
            source_type=SourceType.CASE,
            citation=first_line or slug.replace("-", " ").title(),
            title=first_line or slug,
            source_path=str(path),
        )

    return DocumentMetadata(
        source_type=SourceType.CASE_FILE,
        citation=path.name,
        title=path.name,
        source_path=str(path),
    )


def _chunk_id(text: str, metadata: DocumentMetadata, index: int) -> str:
    h = hashlib.sha1()
    h.update((metadata.citation or "").encode("utf-8"))
    h.update(b"\0")
    h.update(str(index).encode("utf-8"))
    h.update(b"\0")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:16]


def chunk_file(path: Path) -> list[Chunk]:
    """Read one file, infer metadata from its filename, return ready-to-embed chunks."""
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata = metadata_from_path(path)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    pieces = splitter.split_text(text)

    return [
        Chunk(
            id=_chunk_id(piece, metadata, i),
            text=piece,
            metadata=metadata,
            chunk_index=i,
        )
        for i, piece in enumerate(pieces)
    ]
