"""Regression tests for live-data integrity safeguards."""
import unittest

from social_trends import generate_7day_social_history, analyze_buyer_intent


class DataIntegrityTests(unittest.TestCase):
    def test_missing_social_history_is_not_synthesized(self):
        self.assertEqual(generate_7day_social_history("test-product", "Test product"), [])

    def test_empty_comment_set_has_no_positive_buyer_intent(self):
        result = analyze_buyer_intent([])
        self.assertEqual(result["positive_count"], 0)
        self.assertEqual(result["negative_count"], 0)
        self.assertEqual(result["total_analyzed"], 0)


if __name__ == "__main__":
    unittest.main()
