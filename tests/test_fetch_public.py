from __future__ import annotations

import unittest

from ingest.src.fetch_public import extract_cga_section_text, html_to_markdownish


class FetchPublicTests(unittest.TestCase):
    def test_extract_cga_section_text_stops_before_next_section(self) -> None:
        html = """
        <html>
          <body>
            <p><span class="catchln" id="sec_46b-82">Sec. 46b-82. Alimony.</span> (a) First section text.</p>
            <p>(b) More section text.</p>
            <table class="nav_tbl"><tr><td>nav</td></tr></table>
            <p><span class="catchln" id="sec_46b-83">Sec. 46b-83. Temporary support.</span> Other section.</p>
          </body>
        </html>
        """

        text = extract_cga_section_text(html, "46b-82")

        self.assertIn("Sec. 46b-82. Alimony. (a) First section text.", text)
        self.assertIn("(b) More section text.", text)
        self.assertNotIn("46b-83", text)

    def test_html_to_markdownish_keeps_headings_and_lists(self) -> None:
        html = """
        <html>
          <body>
            <h1>Divorce with an Agreement</h1>
            <p>Complete and file the following forms with the court.</p>
            <ul>
              <li>Summons Family Actions (JD-FM-3)</li>
              <li>Divorce Complaint (JD-FM-159)</li>
            </ul>
            <p>Top</p>
          </body>
        </html>
        """

        text = html_to_markdownish(html)

        self.assertIn("# Divorce with an Agreement", text)
        self.assertIn("Complete and file the following forms with the court.", text)
        self.assertIn("- Summons Family Actions (JD-FM-3)", text)
        self.assertIn("- Divorce Complaint (JD-FM-159)", text)
        self.assertNotIn("Top", text)


if __name__ == "__main__":
    unittest.main()
