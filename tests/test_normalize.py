from decimal import Decimal
import unittest

from src.pipelines.normalize import normalize_count, normalize_duration, normalize_rating, normalize_tuition


class NormalizeTest(unittest.TestCase):
    def test_normalize_duration_years(self):
        self.assertEqual(normalize_duration("3 years"), {"duration_value": 3, "duration_unit": "year"})

    def test_normalize_duration_months(self):
        self.assertEqual(normalize_duration("36 months"), {"duration_value": 36, "duration_unit": "month"})

    def test_normalize_tuition_gbp_year(self):
        result = normalize_tuition("£9,250/year")
        self.assertEqual(result["amount"], Decimal("9250.00"))
        self.assertEqual(result["currency"], "GBP")
        self.assertEqual(result["period"], "year")

    def test_normalize_tuition_eur_year(self):
        result = normalize_tuition("EUR 12,000/year")
        self.assertEqual(result["amount"], Decimal("12000.00"))
        self.assertEqual(result["currency"], "EUR")
        self.assertEqual(result["period"], "year")

    def test_normalize_rating(self):
        self.assertEqual(normalize_rating("4.2"), Decimal("4.20"))

    def test_normalize_count_plain_and_k_suffix(self):
        self.assertEqual(normalize_count("1,234"), 1234)
        self.assertEqual(normalize_count("12K"), 12000)


if __name__ == "__main__":
    unittest.main()
