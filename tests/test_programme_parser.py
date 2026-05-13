import unittest
from decimal import Decimal

from src.sources.bachelorsportal.programme_list import parse


PROGRAMME_LIST_HTML = """
<html>
  <body>
    <main>
      <article data-testid="programme-card">
        <a href="/studies/123456/aerospace-engineering-hons-with-professional-placement.html">
          <h2>Aerospace Engineering (Hons) with Professional Placement</h2>
        </a>
        <span data-testid="degree">Bachelor</span>
        <span data-testid="attendance">Full-time</span>
        <span data-testid="delivery">On campus</span>
        <span data-testid="tuition">280,343 CNY / year</span>
        <span data-testid="duration">3 years</span>
        <span data-testid="location">University of Bath Bath, United Kingdom</span>
        <span>Featured</span>
        <span>University of Bath</span>
      </article>
      <article data-testid="programme-card">
        <a href="https://www.bachelorsportal.com/studies/7890/law.html">
          <h3>Law</h3>
        </a>
        <div>B.A.</div>
        <div>Part-time</div>
        <div>Online</div>
        <div>25,983 USD / year</div>
        <div>5 years</div>
        <div class="Location">Plymouth, United Kingdom</div>
      </article>
    </main>
  </body>
</html>
"""


class ProgrammeParserTest(unittest.TestCase):
    def test_programme_name_is_clean_title_only(self):
        records = parse(
            PROGRAMME_LIST_HTML,
            "https://www.bachelorsportal.com/universities/1/example/programmes",
            university_name="University of Bath",
        )

        self.assertEqual(len(records), 2)
        first = records[0]
        self.assertEqual(first["name"], "Aerospace Engineering (Hons) with Professional Placement")
        self.assertNotIn("280,343 CNY", first["name"])
        self.assertNotIn("Featured", first["name"])
        self.assertNotIn("United Kingdom", first["name"])
        self.assertNotIn("Full-time", first["name"])
        self.assertNotIn("University of Bath", first["name"])

    def test_programme_fields_are_extracted_from_card(self):
        records = parse(
            PROGRAMME_LIST_HTML,
            "https://www.bachelorsportal.com/universities/1/example/programmes",
            university_name="University of Bath",
        )

        first = records[0]
        self.assertEqual(first["degree_type"], "Bachelor")
        self.assertEqual(first["attendance_mode"], "Full-time")
        self.assertEqual(first["delivery_mode"], "On Campus")
        self.assertEqual(first["tuition_amount"], Decimal("280343.00"))
        self.assertEqual(first["tuition_currency"], "CNY")
        self.assertEqual(first["tuition_period"], "year")
        self.assertEqual(first["duration_value"], 3)
        self.assertEqual(first["duration_unit"], "year")
        self.assertEqual(first["city"], "Bath")
        self.assertNotIn("University of Bath", first["city"])
        self.assertEqual(first["country"], "United Kingdom")
        self.assertEqual(first["is_featured"], 1)

        second = records[1]
        self.assertEqual(second["name"], "Law")
        self.assertEqual(second["degree_type"], "B.A.")
        self.assertEqual(second["attendance_mode"], "Part-time")
        self.assertEqual(second["delivery_mode"], "Online")
        self.assertEqual(second["tuition_amount"], Decimal("25983.00"))
        self.assertEqual(second["tuition_currency"], "USD")
        self.assertEqual(second["duration_value"], 5)
        self.assertEqual(second["city"], "Plymouth")
        self.assertEqual(second["country"], "United Kingdom")
        self.assertEqual(second["is_featured"], 0)


if __name__ == "__main__":
    unittest.main()
