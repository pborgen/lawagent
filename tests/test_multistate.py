from __future__ import annotations

import unittest

from corpus import available_states, get_state
from ingest.src.public_law import (
    _links_under,
    _section_body,
    _section_number,
    _section_title,
    links_matching,
)
from ingest.src.public_law_tx import _container_links, _tail
from llm import active_collection, collection_for


class CollectionForTests(unittest.TestCase):
    def test_ct_aliases_keep_legacy_base(self) -> None:
        # None / ct / connecticut all map to the legacy ct-divorce base so the
        # existing CT vectors need no re-ingest.
        self.assertEqual(active_collection(), collection_for(None))
        self.assertEqual(collection_for(None), collection_for("ct"))
        self.assertEqual(collection_for("ct"), collection_for("Connecticut"))
        self.assertTrue(collection_for(None).startswith("ct-divorce__"))

    def test_other_states_get_slug_law_base(self) -> None:
        self.assertTrue(collection_for("ny").startswith("ny-law__"))
        # Same embeddings-model suffix as CT — only the base differs.
        suffix = active_collection().split("__", 1)[1]
        self.assertEqual(collection_for("ny"), f"ny-law__{suffix}")


class StateRegistryTests(unittest.TestCase):
    def test_lookup_by_slug_and_name(self) -> None:
        self.assertIn("ny", available_states())
        self.assertEqual(get_state("ny").slug, get_state("New York").slug)
        ny = get_state("ny")
        self.assertEqual(ny.public_law_subdomain, "newyork")
        self.assertTrue(ny.statutes)
        self.assertIn("{section}", ny.statutes[0].citation_format)

    def test_texas_uses_hierarchical_layout(self) -> None:
        tx = get_state("tx")
        self.assertEqual(tx.public_law_subdomain, "texas")
        self.assertEqual(tx.statutes[0].layout, "tx_hierarchical")
        self.assertEqual(tx.statutes[0].citation_format, "Tex. Fam. Code § {section}")

    def test_connecticut_is_rejected(self) -> None:
        # CT uses fetch-public, not the multi-state registry.
        with self.assertRaises(ValueError):
            get_state("connecticut")

    def test_unknown_state_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_state("atlantis")


class PublicLawParserTests(unittest.TestCase):
    TOC = (
        '<a href="n.y._domestic_relations_law_article_10">Art 10</a>'
        '<a href="n.y._domestic_relations_law_article_13">Art 13</a>'
        '<a href="n.y._domestic_relations_law">self</a>'
    )
    ARTICLE = (
        '<a href="n.y._domestic_relations_law_section_170">170</a>'
        '<a href="n.y._domestic_relations_law_section_236">236</a>'
    )
    SECTION = (
        "<title>N.Y. Domestic Relations Law Section 170 – Action for divorce (2026)</title>"
        "<section>An action for divorce may be maintained.</section>"
        "<section>(1) cruel and inhuman treatment.</section>"
    )
    BASE = "https://newyork.public.law/laws/"
    ROOT = "n.y._domestic_relations_law"

    def test_links_under_finds_articles_and_sections(self) -> None:
        arts = _links_under(self.TOC, self.BASE, self.ROOT, "article")
        self.assertEqual(
            arts,
            [
                self.BASE + "n.y._domestic_relations_law_article_10",
                self.BASE + "n.y._domestic_relations_law_article_13",
            ],
        )
        secs = _links_under(self.ARTICLE, self.BASE, self.ROOT, "section")
        self.assertEqual([_section_number(s) for s in secs], ["170", "236"])

    def test_section_number_handles_letter_suffix(self) -> None:
        self.assertEqual(
            _section_number(self.BASE + "n.y._domestic_relations_law_section_236-a"),
            "236-a",
        )

    def test_section_title_strips_label_and_year(self) -> None:
        self.assertEqual(_section_title(self.SECTION), "Action for divorce")

    def test_section_body_joins_section_tags(self) -> None:
        body = _section_body(self.SECTION)
        self.assertIn("An action for divorce may be maintained.", body)
        self.assertIn("(1) cruel and inhuman treatment.", body)


class TexasNavigationTests(unittest.TestCase):
    """Texas reuses the section-page parsers; only navigation differs."""

    BASE = "https://texas.public.law/statutes/"
    ROOT = "tex._fam._code"
    SUBTITLE = (
        '<a href="tex._fam._code_title_1_subtitle_c_chapter_6">Ch 6</a>'
        '<a href="tex._fam._code_title_1_subtitle_c_chapter_7">Ch 7</a>'
        '<a href="tex._fam._code_title_1">up to title</a>'      # breadcrumb (shallower)
        '<a href="tex._fam._code_title_1_subtitle_c_chapter_6_section_6.001">leaf</a>'
    )

    def test_links_matching_finds_sections_at_depth(self) -> None:
        secs = links_matching(self.SUBTITLE, self.BASE, self.ROOT, "_section_")
        self.assertEqual(
            [_section_number(s) for s in secs], ["6.001"]
        )

    def test_container_links_only_descend(self) -> None:
        # From the subtitle page, keep the deeper chapters; drop the shallower
        # breadcrumb (title) and any leaf section link.
        current = "tex._fam._code_title_1_subtitle_c"
        children = _container_links(self.SUBTITLE, self.BASE, self.ROOT, current)
        tails = sorted(_tail(u) for u in children)
        self.assertEqual(
            tails,
            [
                "tex._fam._code_title_1_subtitle_c_chapter_6",
                "tex._fam._code_title_1_subtitle_c_chapter_7",
            ],
        )


if __name__ == "__main__":
    unittest.main()
