from __future__ import annotations

import unittest


class CostLabelTests(unittest.TestCase):
    def test_llm_usage_estimate_label_is_explicit(self) -> None:
        from kb_app.core.costs import format_llm_usage_estimate

        label = format_llm_usage_estimate(0.3429)

        self.assertEqual(
            label,
            "LLM backend usage estimate reported by provider: $0.3429",
        )
        self.assertNotIn("Total cost", label)
        self.assertNotIn("API cost", label)

    def test_zero_llm_usage_estimate_is_clear(self) -> None:
        from kb_app.core.costs import format_llm_usage_estimate

        self.assertEqual(
            format_llm_usage_estimate(0.0),
            "LLM backend usage estimate reported by provider: $0.0000",
        )


if __name__ == "__main__":
    unittest.main()
