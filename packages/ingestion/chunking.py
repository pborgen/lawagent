from __future__ import annotations

import hashlib
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from corpus import AuthorityLevel, Chunk, DocumentMetadata, SourceType


# Filename conventions used by the ingest pipeline to infer source type / citation:
#
#   cgs-46b-82.txt             → STATUTE, citation "Conn. Gen. Stat. § 46b-82"
#   pb-25-26.txt               → PRACTICE_BOOK, citation "Conn. Practice Book § 25-26"
#   case-smith-v-smith.txt     → CASE, citation derived from first line of the file
#   form-jd-fm-159.md          → COURT_FORM
#   guide-divorce-options.md   → COURT_GUIDE
#   lawlib-divorce-guide.md    → LAW_LIBRARY_GUIDE
#   anything-else.txt          → CASE_FILE (treated as the author's own document)
#
# Any inferred value can be overridden with simple frontmatter:
#
#   ---
#   source_type: court_guide
#   authority_level: court_published
#   citation: Divorce Options in Connecticut
#   title: Divorce Options in Connecticut
#   issuing_body: Connecticut Judicial Branch
#   topic: divorce-process
#   stage: pre-filing
#   document_id: FM-274
#   ---

_CGS_RE = re.compile(r"^cgs-([0-9a-z\-]+)$", re.IGNORECASE)
_PB_RE = re.compile(r"^pb-([0-9a-z\-]+)$", re.IGNORECASE)
_CASE_RE = re.compile(r"^case-(.+)$", re.IGNORECASE)
_FORM_RE = re.compile(r"^form-(.+)$", re.IGNORECASE)
_GUIDE_RE = re.compile(r"^guide-(.+)$", re.IGNORECASE)
_LAWLIB_RE = re.compile(r"^(?:lawlib|research)-(.+)$", re.IGNORECASE)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n?", re.DOTALL)
_SECTION_RE = re.compile(r"(?m)^Sec\. (?P<section>[0-9A-Za-z\-]+)\.")
_TOP_LEVEL_SUBSECTION_RE = re.compile(r"(?m)^\((?P<subsection>[a-z])\)\s")

_TEXT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _clean_slug(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").strip()


def _clean_title(slug: str) -> str:
    return _clean_slug(slug).title()


def _parse_frontmatter(raw_text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(raw_text)
    if not match:
        return {}, raw_text

    metadata: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, raw_text[match.end() :]


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _citation_for(source_type: SourceType, section: str, subsection: str | None = None) -> str:
    suffix = subsection or ""
    if source_type == SourceType.STATUTE:
        return f"Conn. Gen. Stat. § {section}{suffix}"
    if source_type == SourceType.PRACTICE_BOOK:
        return f"Conn. Practice Book § {section}{suffix}"
    return section


def _subsection_citation(base_citation: str, subsection: str) -> str:
    """Cite a subsection by appending to the section's own citation.

    Deriving from the document's existing citation (rather than rebuilding a
    hardcoded jurisdiction prefix) keeps this state-agnostic: a CT section
    cited `Conn. Gen. Stat. § 46b-82` yields `…§ 46b-82(a)` (byte-identical
    to the old hardcoded path), while a NY section cited
    `N.Y. Dom. Rel. Law § 236` yields `…§ 236(a)` instead of corrupting it
    into a Connecticut citation.
    """
    return f"{base_citation}{subsection}"


def _apply_metadata_overrides(
    metadata: DocumentMetadata,
    overrides: dict[str, str | None],
) -> DocumentMetadata:
    payload = metadata.model_dump()
    allowed_keys = set(DocumentMetadata.model_fields)
    for key, value in overrides.items():
        if value is None or key not in allowed_keys:
            continue
        payload[key] = value
    return DocumentMetadata(**payload)


def metadata_from_path(
    path: Path,
    *,
    text: str | None = None,
    overrides: dict[str, str] | None = None,
) -> DocumentMetadata:
    stem = path.stem.lower()

    if m := _CGS_RE.match(stem):
        section = m.group(1)
        metadata = DocumentMetadata(
            source_type=SourceType.STATUTE,
            authority_level=AuthorityLevel.PRIMARY,
            citation=f"Conn. Gen. Stat. § {section}",
            title=f"CGS § {section}",
            section=section,
            jurisdiction="Connecticut",
            issuing_body="Connecticut General Assembly",
            source_path=str(path),
        )
        return _apply_metadata_overrides(metadata, overrides or {})

    if m := _PB_RE.match(stem):
        section = m.group(1)
        metadata = DocumentMetadata(
            source_type=SourceType.PRACTICE_BOOK,
            authority_level=AuthorityLevel.COURT_RULE,
            citation=f"Conn. Practice Book § {section}",
            title=f"Practice Book § {section}",
            section=section,
            jurisdiction="Connecticut",
            issuing_body="Connecticut Judicial Branch",
            source_path=str(path),
        )
        return _apply_metadata_overrides(metadata, overrides or {})

    if m := _CASE_RE.match(stem):
        slug = m.group(1)
        first_line = _first_nonempty_line(text or "")
        metadata = DocumentMetadata(
            source_type=SourceType.CASE,
            authority_level=AuthorityLevel.PRIMARY,
            citation=first_line or slug.replace("-", " ").title(),
            title=first_line or slug,
            jurisdiction="Connecticut",
            issuing_body="Connecticut Appellate Courts",
            source_path=str(path),
        )
        return _apply_metadata_overrides(metadata, overrides or {})

    if m := _FORM_RE.match(stem):
        slug = m.group(1)
        document_id = slug.upper()
        metadata = DocumentMetadata(
            source_type=SourceType.COURT_FORM,
            authority_level=AuthorityLevel.COURT_PUBLISHED,
            citation=f"Conn. Judicial Branch Form {document_id}",
            title=_clean_title(slug),
            jurisdiction="Connecticut",
            issuing_body="Connecticut Judicial Branch",
            document_id=document_id,
            source_path=str(path),
        )
        return _apply_metadata_overrides(metadata, overrides or {})

    if m := _GUIDE_RE.match(stem):
        slug = m.group(1)
        metadata = DocumentMetadata(
            source_type=SourceType.COURT_GUIDE,
            authority_level=AuthorityLevel.COURT_PUBLISHED,
            citation=_clean_title(slug),
            title=_clean_title(slug),
            jurisdiction="Connecticut",
            issuing_body="Connecticut Judicial Branch",
            source_path=str(path),
        )
        return _apply_metadata_overrides(metadata, overrides or {})

    if m := _LAWLIB_RE.match(stem):
        slug = m.group(1)
        metadata = DocumentMetadata(
            source_type=SourceType.LAW_LIBRARY_GUIDE,
            authority_level=AuthorityLevel.SECONDARY,
            citation=_clean_title(slug),
            title=_clean_title(slug),
            jurisdiction="Connecticut",
            issuing_body="Connecticut Judicial Branch Law Libraries",
            source_path=str(path),
        )
        return _apply_metadata_overrides(metadata, overrides or {})

    metadata = DocumentMetadata(
        source_type=SourceType.CASE_FILE,
        authority_level=AuthorityLevel.PERSONAL,
        citation=path.name,
        title=path.name,
        source_path=str(path),
    )
    return _apply_metadata_overrides(metadata, overrides or {})


def _chunk_id(text: str, metadata: DocumentMetadata, index: int) -> str:
    h = hashlib.sha1()
    h.update((metadata.citation or "").encode("utf-8"))
    h.update(b"\0")
    h.update(str(index).encode("utf-8"))
    h.update(b"\0")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:16]


def _split_on_matches(text: str, pattern: re.Pattern[str], group: str) -> list[tuple[str, str]]:
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block_text = text[start:end].strip()
        if block_text:
            blocks.append((match.group(group), block_text))
    return blocks


def _append_text_chunks(chunks: list[Chunk], text: str, metadata: DocumentMetadata) -> None:
    normalized = text.strip()
    if not normalized:
        return

    pieces = [piece.strip() for piece in _TEXT_SPLITTER.split_text(normalized) if piece.strip()]
    for piece in pieces:
        index = len(chunks)
        chunks.append(
            Chunk(
                id=_chunk_id(piece, metadata, index),
                text=piece,
                metadata=metadata,
                chunk_index=index,
            )
        )


def _chunk_section_text(
    section_text: str,
    metadata: DocumentMetadata,
    chunks: list[Chunk],
) -> None:
    subsection_blocks = _split_on_matches(section_text, _TOP_LEVEL_SUBSECTION_RE, "subsection")
    if not subsection_blocks:
        _append_text_chunks(chunks, section_text, metadata)
        return

    first_subsection = _TOP_LEVEL_SUBSECTION_RE.search(section_text)
    preamble = section_text[: first_subsection.start()].strip() if first_subsection else ""

    for subsection, block_text in subsection_blocks:
        subsection_value = f"({subsection})"
        block_with_context = (
            f"{preamble}\n\n{block_text}".strip() if preamble else block_text.strip()
        )
        subsection_metadata = _apply_metadata_overrides(
            metadata,
            {
                "subsection": subsection_value,
                "citation": _subsection_citation(metadata.citation, subsection_value),
            },
        )
        _append_text_chunks(chunks, block_with_context, subsection_metadata)


def _chunk_statute_like_text(text: str, metadata: DocumentMetadata) -> list[Chunk]:
    chunks: list[Chunk] = []
    section_blocks = _split_on_matches(text, _SECTION_RE, "section")

    if not section_blocks:
        # No `Sec. N.` headings. This is the shape of a public.law-sourced
        # statute (one section per file, citation already in frontmatter).
        # Chunk it as plain text so we keep that section-level citation —
        # do NOT run the CT subsection splitter, whose `(a)`-style regex
        # would mis-split inline enumerations (e.g. NY DRL § 170's nested
        # `(a)`,`(b)` under subdivision (6)) into fabricated `§ 170(a)`
        # citations. CT statute/Practice Book files always carry `Sec. N.`
        # headings, so they take the section-aware path below.
        _append_text_chunks(chunks, text, metadata)
        return chunks

    for section, section_text in section_blocks:
        section_metadata = _apply_metadata_overrides(
            metadata,
            {
                "section": section,
                "citation": _citation_for(metadata.source_type, section),
                "title": _first_nonempty_line(section_text) or metadata.title,
            },
        )
        _chunk_section_text(section_text, section_metadata, chunks)

    return chunks


def chunk_file(path: Path) -> list[Chunk]:
    """Read one file, infer metadata, and return citation-preserving chunks."""
    raw_text = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    overrides, text = _parse_frontmatter(raw_text)
    metadata = metadata_from_path(path, text=text, overrides=overrides)

    if metadata.source_type in {SourceType.STATUTE, SourceType.PRACTICE_BOOK}:
        return _chunk_statute_like_text(text, metadata)

    chunks: list[Chunk] = []
    _append_text_chunks(chunks, text, metadata)
    return chunks
