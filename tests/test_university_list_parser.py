import unittest

from src.sources.bachelorsportal.university_list import build_university_search_url, parse


HTML_FIXTURE = """
<html>
  <body>
    <main>
      <article data-testid="university-card">
        <a href="/universities/123/university-of-example.html">
          <h2>University of Example</h2>
        </a>
        <span data-testid="location">London, United Kingdom</span>
        <span>125 Bachelors</span>
        <span>18 Scholarships</span>
        <span>Rating 4.3</span>
        <span>1,234 reviews</span>
        <p>A public research university in London.</p>
      </article>
      <article data-testid="university-card">
        <a href="https://www.bachelorsportal.com/universities/456/sample-college.html">
          Sample College
        </a>
        <div class="Location">Manchester, United Kingdom</div>
        <div>Bachelors 42</div>
        <div>Scholarships 7</div>
        <div>4.1 / 5</div>
        <div>Reviews: 98</div>
      </article>
    </main>
  </body>
</html>
"""


class UniversityListParserTest(unittest.TestCase):
    def test_build_university_search_url_uses_country_path(self):
        self.assertEqual(
            build_university_search_url("united-kingdom"),
            "https://www.bachelorsportal.com/search/universities/bachelor/united-kingdom",
        )

    def test_parse_university_cards_extracts_required_identity_and_metrics(self):
        records = parse(HTML_FIXTURE, "https://www.bachelorsportal.com/search/universities/bachelor/united-kingdom")

        self.assertEqual(len(records), 2)
        first = records[0]
        self.assertEqual(first["name"], "University of Example")
        self.assertEqual(first["source_url"], "https://www.bachelorsportal.com/universities/123/university-of-example.html")
        self.assertEqual(first["source_university_id"], "123")
        self.assertEqual(first["country"], "United Kingdom")
        self.assertEqual(first["city"], "London")
        self.assertEqual(first["location_text"], "London, United Kingdom")
        self.assertEqual(first["bachelor_count"], 125)
        self.assertEqual(first["scholarship_count"], 18)
        self.assertEqual(str(first["rating"]), "4.30")
        self.assertEqual(first["review_count"], 1234)

        second = records[1]
        self.assertEqual(second["name"], "Sample College")
        self.assertEqual(second["source_university_id"], "456")
        self.assertEqual(second["city"], "Manchester")
        self.assertEqual(second["bachelor_count"], 42)
        self.assertEqual(second["scholarship_count"], 7)
        self.assertEqual(str(second["rating"]), "4.10")
        self.assertEqual(second["review_count"], 98)


if __name__ == "__main__":
    unittest.main()
