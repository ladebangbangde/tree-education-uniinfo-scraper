import contextlib
import io
import unittest
from decimal import Decimal

from src.sources.bachelorsportal.parser import soupify
from src.sources.bachelorsportal.programme_detail import (
    _quick_fact_label_value_map,
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


QUICK_FACT_COMPONENT_HTML = """
<html>
  <body>
    <div class="QuickFactComponent RowComponent js-quickFactComponent">
      <div class="Label">Tuition fee</div>
      <div class="ValueContainer">
        <div class="Value">
          <div class="TuitionFeeContainer">
            <span data-currency="GBP">24,224 USD / year</span>
          </div>
        </div>
      </div>
    </div>
    <div class="QuickFactComponent RowComponent js-quickFactComponent">
      <div class="Label">Duration</div>
      <div class="ValueContainer"><div class="Value">3 years</div></div>
    </div>
    <div class="QuickFactComponent RowComponent js-quickFactComponent">
      <div class="Label">Apply date</div>
      <div class="ValueContainer">
        <div class="Value">
          <time datetime="2026-06-30">Jun 2026</time>
          <div class="TimingContainer js-notAvailable Unknown Hidden">Unknown</div>
        </div>
      </div>
    </div>
    <div class="QuickFactComponent RowComponent js-quickFactComponent">
      <div class="Label">Start date</div>
      <div class="ValueContainer">
        <div class="Value">
          <time datetime="2026-09-01">Sep 2026</time>
          <div class="TimingContainer js-notAvailable Unknown Hidden">Unknown</div>
        </div>
      </div>
    </div>
    <div class="QuickFactComponent RowComponent js-quickFactComponent">
      <div class="Label">Campus location</div>
      <div class="ValueContainer"><div class="Value">Portsmouth, United Kingdom</div></div>
    </div>
    <div class="QuickFactComponent RowComponent js-quickFactComponent">
      <div class="Label">Taught in</div>
      <div class="ValueContainer"><div class="Value">English</div></div>
    </div>
    <div class="QuickFactComponent RowComponent js-quickFactComponent">
      <div class="Button">
        <span class="ScholarshipsAvailableIncentiveLabel">Scholarships available</span>
        <button disabled>Check eligibility</button>
      </div>
    </div>
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

    def test_quick_fact_components_ignore_hidden_unknown_and_parse_tuition_scholarships(self):
        facts = parse_facts_summary(QUICK_FACT_COMPONENT_HTML)

        self.assertEqual(facts["tuition_amount"], Decimal("24224.00"))
        self.assertEqual(facts["tuition_currency"], "USD")
        self.assertEqual(facts["tuition_period"], "year")
        self.assertEqual(facts["tuition_text_raw"], "24,224 USD / year")
        self.assertEqual(facts["duration_value"], 3)
        self.assertEqual(facts["duration_unit"], "year")
        self.assertEqual(facts["apply_date_text"], "Jun 2026")
        self.assertEqual(facts["start_date_text"], "Sep 2026")
        self.assertEqual(facts["city"], "Portsmouth")
        self.assertEqual(facts["country"], "United Kingdom")
        self.assertEqual(facts["teaching_language"], "English")
        self.assertEqual(facts["scholarships_available"], 1)

    def test_quick_fact_label_map_uses_only_label_and_value_nodes(self):
        html = """
            <html><body>
              <div class="QuickFactComponent">
                <div class="Label">Tuition fee</div>
                <div class="ValueContainer">
                  <div class="Value">
                    <span class="Title" data-amount="164451">164,451</span>
                    <span class="CurrencyType">CNY</span>
                    <span class="Unit">/ year</span>
                  </div>
                </div>
                <div class="Button">
                  <button class="Label">Scholarships available</button>
                  <span class="ScholarshipsAvailableIncentiveLabel">Scholarships available</span>
                </div>
              </div>
              <div class="QuickFactComponent">
                <div class="Label">Duration</div>
                <div class="ValueContainer"><div class="Value">3 years</div></div>
              </div>
              <div class="QuickFactComponent">
                <div class="Label">Apply date</div>
                <div class="ValueContainer"><div class="Value">Jun 2026</div></div>
              </div>
              <div class="QuickFactComponent">
                <div class="Label">Start date</div>
                <div class="ValueContainer"><div class="Value">Sep 2026</div></div>
              </div>
              <div class="QuickFactComponent">
                <div class="Label">Campus location</div>
                <div class="ValueContainer"><div class="Value">Portsmouth, United Kingdom</div></div>
              </div>
              <div class="QuickFactComponent">
                <div class="Label">Taught in</div>
                <div class="ValueContainer"><div class="Value">English</div></div>
              </div>
            </body></html>
        """

        label_map = _quick_fact_label_value_map(soupify(html))
        facts = parse_facts_summary(html)

        self.assertEqual(
            label_map,
            {
                "Tuition fee": "164,451 CNY / year",
                "Duration": "3 years",
                "Apply date": "Jun 2026",
                "Start date": "Sep 2026",
                "Campus location": "Portsmouth, United Kingdom",
                "Taught in": "English",
            },
        )
        self.assertEqual(facts["tuition_amount"], Decimal("164451.00"))
        self.assertEqual(facts["tuition_currency"], "CNY")
        self.assertEqual(facts["tuition_period"], "year")
        self.assertEqual(facts["tuition_text_raw"], "164,451 CNY / year")
        self.assertEqual(facts["scholarships_available"], 1)

    def test_quick_fact_tuition_parser_supports_cny_and_ignores_hidden_nodes(self):
        facts = parse_facts_summary(
            """
            <html><body>
              <div class="QuickFactComponent RowComponent js-quickFactComponent">
                <div class="Label">Tuition fee</div>
                <div class="ValueContainer">
                  <div class="Value">
                    <div class="TuitionFeeContainer">
                      <span data-currency="CNY">280,343 CNY / year</span>
                      <span class="Hidden Unknown js-notAvailable">Unknown</span>
                    </div>
                  </div>
                </div>
              </div>
            </body></html>
            """
        )

        self.assertEqual(facts["tuition_amount"], Decimal("280343.00"))
        self.assertEqual(facts["tuition_currency"], "CNY")
        self.assertEqual(facts["tuition_period"], "year")
        self.assertEqual(facts["tuition_text_raw"], "280,343 CNY / year")

    def test_quick_fact_tuition_uses_original_html_when_visible_text_has_no_amount(self):
        html = """
            <html><body>
              <div class="QuickFactComponent RowComponent js-quickFactComponent">
                <div class="Label">Tuition fee</div>
                <div class="ValueContainer">
                  <div class="Value">
                    <span data-currency="GBP" data-original_html="17,900 GBP">View fees</span>
                    <span class="Unit">/ year</span>
                    <span class="Hidden Unknown js-notAvailable">Unknown</span>
                  </div>
                </div>
              </div>
            </body></html>
        """
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            facts = parse_facts_summary(html)

        self.assertIn('class="QuickFactComponent RowComponent js-quickFactComponent"', stdout.getvalue())
        self.assertIn('data-original_html="17,900 GBP"', stdout.getvalue())
        self.assertEqual(facts["tuition_amount"], Decimal("17900.00"))
        self.assertEqual(facts["tuition_currency"], "GBP")
        self.assertEqual(facts["tuition_period"], "year")
        self.assertEqual(facts["tuition_text_raw"], "17,900 GBP / year")

    def test_tuition_parser_supports_gbp_year_values(self):
        parsed = parse_tuition_fact("17,900 GBP / year")

        self.assertEqual(parsed["amount"], Decimal("17900.00"))
        self.assertEqual(parsed["currency"], "GBP")
        self.assertEqual(parsed["period"], "year")
        self.assertEqual(parsed["raw"], "17,900 GBP / year")

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
