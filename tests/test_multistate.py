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
from ingest.src.public_law_flat import _section_links_flat
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

    def test_all_states_present(self) -> None:
        self.assertEqual(
            set(available_states()),
            {"ny", "tx", "ca", "fl", "or", "co", "nv", "ct",
             "il", "oh", "pa", "nc", "mi", "va", "wa", "az"},
        )

    def test_every_official_state_has_a_registered_handler(self) -> None:
        # Every fetcher="official" state must name a handler wired in main.py
        # (ct_bespoke is handled by the fetch-public delegation, not the map).
        from ingest.main import _OFFICIAL_CRAWLERS
        for slug in available_states():
            st = get_state(slug)
            if st.fetcher != "official":
                continue
            if st.official_handler == "ct_bespoke":
                self.assertEqual(slug, "ct")
                continue
            self.assertIn(st.official_handler, _OFFICIAL_CRAWLERS, slug)
            self.assertTrue(collection_for(slug).startswith(f"{slug}-law__"), slug)

    def test_layouts_and_schemes(self) -> None:
        cases = {
            "ny": ("ny_article", "/laws/"),
            "tx": ("tx_hierarchical", "/statutes/"),
            "ca": ("tx_hierarchical", "/codes/"),
            "fl": ("flat_section", "/statutes/"),
            "or": ("flat_section", "/statutes/"),
            "co": ("flat_section", "/statutes/"),
            "nv": ("flat_section", "/statutes/"),
        }
        for slug, (layout, base) in cases.items():
            code = get_state(slug).statutes[0]
            self.assertEqual(code.layout, layout, slug)
            self.assertEqual(code.base_path, base, slug)
            if layout == "flat_section":
                self.assertTrue(code.section_prefix, f"{slug} needs section_prefix")

    def test_connecticut_uses_official_fetcher(self) -> None:
        ct = get_state("ct")
        self.assertEqual(ct.fetcher, "official")
        # CT routes to the legacy collection, not ct-law.
        self.assertTrue(collection_for("ct").startswith("ct-divorce__"))

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

    def test_section_number_across_layouts(self) -> None:
        # _section_ token (NY/TX/CA) vs flat slugs (FL/OR/CO/NV).
        cases = {
            "https://x/codes/family_code_section_2310": "2310",
            "https://x/statutes/tex._fam._code_section_9.001": "9.001",
            "https://x/statutes/fla._stat._61.08": "61.08",
            "https://x/statutes/ors_107.105": "107.105",
            "https://x/statutes/crs_14-10-106": "14-10-106",
            "https://x/statutes/nrs_125.180": "125.180",
        }
        for url, expected in cases.items():
            self.assertEqual(_section_number(url), expected, url)

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


class FlatSectionNavigationTests(unittest.TestCase):
    """FL/OR/CO/NV: section links are <prefix>_<digit>, containers are not."""

    BASE = "https://oregon.public.law/statutes/"

    def test_section_links_flat_picks_only_numbered_slugs(self) -> None:
        html = (
            '<a href="ors_107.005">107.005</a>'
            '<a href="ors_107.105">107.105</a>'
            '<a href="ors_chapter_107">chapter (container)</a>'
            '<a href="ors_title_11">title (container)</a>'
            '<a href="ors_volume_3">volume (container)</a>'
        )
        secs = _section_links_flat(html, self.BASE, "ors")
        self.assertEqual(
            [_section_number(s) for s in secs], ["107.005", "107.105"]
        )

    def test_section_links_flat_handles_dotted_prefix(self) -> None:
        # Florida's prefix itself contains dots: fla._stat._61.08
        html = (
            '<a href="fla._stat._61.08">61.08</a>'
            '<a href="fla._stat._chapter_61">chapter (container)</a>'
        )
        secs = _section_links_flat(html, "https://florida.public.law/statutes/", "fla._stat.")
        self.assertEqual([_section_number(s) for s in secs], ["61.08"])


if __name__ == "__main__":
    unittest.main()
