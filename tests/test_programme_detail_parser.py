import unittest
from decimal import Decimal

from src.sources.bachelorsportal.programme_detail import (
    parse,
    parse_facts_summary,
    parse_location_fact,
    parse_tuition_fact,
)


DETAIL_HTML = """
<html>
  <body>
    <aside data-testid="programme-facts-card">
      <div><span>Tuition fee</span>: <strong>41,275 USD / year</strong></div>
      <div>Scholarships available</div>
      <div><span>Duration</span>: <strong>4 years</strong></div>
      <div><span>Apply date</span>: <strong>Jan 2027</strong></div>
      <div><span>Start date</span>: <strong>Sep 2027</strong></div>
      <div><span>Campus location</span>: <strong>Bath, United Kingdom</strong></div>
      <div><span>Taught in</span>: <strong>English</strong></div>
    </aside>
  </body>
</html>
"""


DETAIL_TEXT_BLOCK_HTML = """
<html>
  <body>
    <aside data-testid="programme-facts-card">
      Tuition fee
      24,224 USD / year
      Scholarships available

      Duration
      3 years

      Apply date
      Jun 2026

      Start date
      Sep 2026

      Campus location
      Portsmouth, United Kingdom

      Taught in
      English
    </aside>
    <section>
      <h2>Overview</h2>
      <p>This overview mentions English and September but must not drive fact parsing.</p>
    </section>
  </body>
</html>
"""


class ProgrammeDetailParserTest(unittest.TestCase):
    def test_facts_card_example_html_is_parsed(self):
        record = parse(DETAIL_HTML, "https://www.bachelorsportal.com/studies/15/example.html")
        programme = record["programme"]

        self.assertEqual(programme["tuition_amount"], Decimal("41275.00"))
        self.assertEqual(programme["tuition_currency"], "USD")
        self.assertEqual(programme["tuition_period"], "year")
        self.assertEqual(programme["tuition_text_raw"], "41,275 USD / year")
        self.assertEqual(programme["duration_value"], 4)
        self.assertEqual(programme["duration_unit"], "year")
        self.assertEqual(programme["duration_text_raw"], "4 years")
        self.assertEqual(programme["apply_date_text"], "Jan 2027")
        self.assertEqual(programme["start_date_text"], "Sep 2027")
        self.assertEqual(programme["city"], "Bath")
        self.assertEqual(programme["country"], "United Kingdom")
        self.assertEqual(programme["teaching_language"], "English")
        self.assertEqual(programme["scholarships_available"], 1)
        self.assertEqual(record["intake"]["apply_date_text"], "Jan 2027")
        self.assertEqual(record["intake"]["start_date_text"], "Sep 2027")
        self.assertEqual(record["language_requirement"]["teaching_language"], "English")


    def test_facts_summary_text_block_is_parsed_from_top_card(self):
        facts = parse_facts_summary(DETAIL_TEXT_BLOCK_HTML)

        self.assertEqual(facts["tuition_amount"], Decimal("24224.00"))
        self.assertEqual(facts["tuition_currency"], "USD")
        self.assertEqual(facts["tuition_period"], "year")
        self.assertEqual(facts["tuition_text_raw"], "24,224 USD / year")
        self.assertEqual(facts["duration_value"], 3)
        self.assertEqual(facts["duration_unit"], "year")
        self.assertEqual(facts["duration_text_raw"], "3 years")
        self.assertEqual(facts["apply_date_text"], "Jun 2026")
        self.assertEqual(facts["start_date_text"], "Sep 2026")
        self.assertEqual(facts["city"], "Portsmouth")
        self.assertEqual(facts["country"], "United Kingdom")
        self.assertEqual(facts["teaching_language"], "English")
        self.assertEqual(facts["scholarships_available"], 1)

    def test_facts_summary_does_not_parse_unscoped_overview_text(self):
        facts = parse_facts_summary(
            """
            <html><body>
              <section>
                <h2>Overview</h2>
                <p>Tuition fee 99,999 USD / year Duration 9 years Taught in English</p>
              </section>
            </body></html>
            """
        )

        self.assertIsNone(facts["tuition_amount"])
        self.assertIsNone(facts["duration_value"])
        self.assertIsNone(facts["teaching_language"])

    def test_missing_fields_return_none_without_error(self):
        record = parse('<html><body><aside data-testid="programme-facts-card"><div>Duration: 4 years</div></aside></body></html>', "https://example.test")
        programme = record["programme"]

        self.assertIsNone(programme["tuition_amount"])
        self.assertIsNone(programme["tuition_currency"])
        self.assertIsNone(programme["tuition_period"])
        self.assertEqual(programme["duration_value"], 4)
        self.assertIsNone(programme["apply_date_text"])
        self.assertIsNone(programme["start_date_text"])
        self.assertIsNone(programme["city"])
        self.assertIsNone(programme["country"])
        self.assertIsNone(programme["teaching_language"])
        self.assertIsNone(programme["scholarships_available"])

    def test_location_parser_splits_city_and_country(self):
        parsed = parse_location_fact("Bath, United Kingdom")

        self.assertEqual(parsed["city"], "Bath")
        self.assertEqual(parsed["country"], "United Kingdom")

    def test_tuition_parser_normalizes_amount_currency_period(self):
        parsed = parse_tuition_fact("41,275 USD / year")

        self.assertEqual(parsed["amount"], Decimal("41275.00"))
        self.assertEqual(parsed["currency"], "USD")
        self.assertEqual(parsed["period"], "year")


if __name__ == "__main__":
    unittest.main()
