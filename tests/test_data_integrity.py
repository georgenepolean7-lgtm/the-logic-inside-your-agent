"""Regression tests for live-data integrity safeguards."""
import unittest

from social_trends import generate_7day_social_history, analyze_buyer_intent
from analyzer import evaluate_rule_based_signals


class DataIntegrityTests(unittest.TestCase):
    def test_missing_social_history_is_not_synthesized(self):
        self.assertEqual(generate_7day_social_history("test-product", "Test product"), [])

    def test_missing_core_metrics_cannot_be_website_ready(self):
        result = evaluate_rule_based_signals({"price": 299, "rating": None, "review_count": None})
        self.assertFalse(result["website_ready"])
        self.assertEqual(result["sellability_score"], 25)
        self.assertIn("missing", result["ai_reasoning"].lower())

    def test_empty_comment_set_has_no_positive_buyer_intent(self):
        result = analyze_buyer_intent([])
        self.assertEqual(result["positive_count"], 0)
        self.assertEqual(result["negative_count"], 0)
        self.assertEqual(result["total_analyzed"], 0)
        self.assertIsNone(result["intent_score"])
        self.assertIn("Unavailable", result["dominant_phrase"])


if __name__ == "__main__":
    unittest.main()
