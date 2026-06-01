from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from corpus import AuthorityLevel, SourceType
from ingestion.chunking import chunk_file


class IngestionChunkingTests(unittest.TestCase):
    def test_statute_file_splits_by_top_level_subsection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cgs-46b-82.txt"
            path.write_text(
                "\n".join(
                    [
                        "Sec. 46b-82. Alimony.",
                        "",
                        "(a) At the time of entering the decree, the Superior Court may order alimony.",
                        "",
                        "(b) If the court enters an order that lasts until death or remarriage,",
                        "the court shall articulate the basis for the order.",
                    ]
                ),
                encoding="utf-8",
            )

            chunks = chunk_file(path)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].metadata.source_type, SourceType.STATUTE)
        self.assertEqual(chunks[0].metadata.section, "46b-82")
        self.assertEqual(chunks[0].metadata.subsection, "(a)")
        self.assertEqual(chunks[0].metadata.citation, "Conn. Gen. Stat. § 46b-82(a)")
        self.assertEqual(chunks[1].metadata.subsection, "(b)")
        self.assertEqual(chunks[1].metadata.citation, "Conn. Gen. Stat. § 46b-82(b)")

    def test_non_ct_statute_keeps_frontmatter_citation(self) -> None:
        # A public.law-sourced statute (one section per file, no `Sec. N.`
        # heading) carries its own citation in frontmatter. Every chunk must
        # keep THAT section-level citation — never a hardcoded Connecticut
        # prefix, and never a fabricated subsection cite from inline `(a)`
        # enumerations (cf. NY DRL § 170's nested `(a)` under subdivision 6).
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nydrl-170.txt"
            path.write_text(
                "\n".join(
                    [
                        "---",
                        "source_type: statute",
                        "authority_level: primary",
                        "citation: N.Y. Dom. Rel. Law § 170",
                        "title: Action for divorce",
                        "section: 170",
                        "jurisdiction: New York",
                        "issuing_body: New York State Legislature",
                        "---",
                        "An action for divorce may be maintained on any of the following grounds:",
                        "",
                        "(6) The spouses have lived apart pursuant to a written agreement "
                        "of separation that recites:",
                        "",
                        "(a) the names and addresses of each of the parties,",
                        "",
                        "(b) the date of marriage of the parties.",
                    ]
                ),
                encoding="utf-8",
            )

            chunks = chunk_file(path)

        self.assertTrue(chunks)
        for chunk in chunks:
            self.assertEqual(chunk.metadata.source_type, SourceType.STATUTE)
            self.assertEqual(chunk.metadata.jurisdiction, "New York")
            self.assertEqual(chunk.metadata.citation, "N.Y. Dom. Rel. Law § 170")
            self.assertNotIn("Conn.", chunk.metadata.citation)

    def test_frontmatter_overrides_filename_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "guide-divorce-options.md"
            path.write_text(
                "\n".join(
                    [
                        "---",
                        "source_type: court_guide",
                        "authority_level: court_published",
                        "citation: Divorce Options in Connecticut",
                        "title: Divorce Options in Connecticut",
                        "topic: divorce-process",
                        "stage: pre-filing",
                        "document_id: FM-274",
                        "---",
                        "This is a plain-English overview of divorce options in Connecticut.",
                    ]
                ),
                encoding="utf-8",
            )

            chunks = chunk_file(path)

        self.assertEqual(len(chunks), 1)
        metadata = chunks[0].metadata
        self.assertEqual(metadata.source_type, SourceType.COURT_GUIDE)
        self.assertEqual(metadata.authority_level, AuthorityLevel.COURT_PUBLISHED)
        self.assertEqual(metadata.citation, "Divorce Options in Connecticut")
        self.assertEqual(metadata.topic, "divorce-process")
        self.assertEqual(metadata.stage, "pre-filing")
        self.assertEqual(metadata.document_id, "FM-274")


if __name__ == "__main__":
    unittest.main()
