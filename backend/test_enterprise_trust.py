import unittest
from unittest.mock import patch

from app.evidence import build_tool_evidence
from app.session_store import summarize_tool_result
from app.writeback_preview import _prepare_email_campaign, _preview_discount_rule


class EnterpriseTrustTests(unittest.TestCase):
    @patch("app.writeback_preview._sales_units", return_value=9)
    @patch(
        "app.writeback_preview._product_template",
        return_value={"id": 10, "name": "Wool Coat", "list_price": 180, "standard_price": 81},
    )
    def test_discount_preview_contains_diff_and_risk_notes(self, _product_template, _sales_units):
        preview = _preview_discount_rule({
            "products": ["Wool Coat"],
            "discount_percent": 15,
            "min_quantity": 1,
        })

        self.assertEqual(preview["odoo_model"], "product.pricelist.item")
        self.assertEqual(preview["operation"], "create_discount_items")
        self.assertEqual(preview["records"][0]["changes"][1]["old_value"], 180)
        self.assertEqual(preview["records"][0]["changes"][1]["new_value"], 153)
        self.assertTrue(preview["risk_notes"])

    @patch(
        "app.writeback_preview._email_segment",
        return_value={
            "recipient_count": 42,
            "mailing_domain": "[['id', 'in', [1, 2]]]",
            "label": "Customers who bought Outerwear",
        },
    )
    def test_email_prepare_is_draft_only_with_recipient_count(self, _email_segment):
        payload, preview = _prepare_email_campaign({
            "subject": "Fresh stock",
            "body_html": "<p>Back in stock</p>",
            "segment": "Outerwear",
        })

        self.assertEqual(payload["recipient_count"], 42)
        self.assertEqual(preview["odoo_model"], "mailing.mailing")
        self.assertIn("Never auto-sends", " ".join(preview["expected_impact"]))
        self.assertEqual(preview["records"][0]["changes"][2]["new_value"], "draft")

    def test_sql_evidence_keeps_top_rows_and_sql(self):
        evidence = build_tool_evidence(
            "sql_analytics",
            {"sql": "SELECT 1 AS answer"},
            {"row_count": 1, "rows": [{"answer": 1}]},
            summary="Tool context: returned one row.",
        )

        self.assertEqual(evidence["rows_returned"], 1)
        self.assertEqual(evidence["top_rows"], [{"answer": 1}])
        self.assertEqual(evidence["sql"], "SELECT 1 AS answer")

    def test_summarizes_discount_simulation_for_memory(self):
        summary = summarize_tool_result(
            "simulate_discount_impact",
            {"products": ["Wool Coat"], "discount_percent": 15},
            {
                "products": [{"product": "Wool Coat"}],
                "totals": {"revenue_delta": 120, "margin_delta": -18},
            },
        )

        self.assertIn("simulate_discount_impact evaluated 1 products", summary)
        self.assertIn("margin delta -18", summary)


if __name__ == "__main__":
    unittest.main()
