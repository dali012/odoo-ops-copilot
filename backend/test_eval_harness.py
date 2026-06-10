import unittest
from unittest.mock import patch

from app.eval_harness import (
    contains_number_near,
    grade_active_product_count,
    grade_inventory_aging_top_dead_stock,
    grade_margin_top_category_gross_profit,
    grade_schema_sales_by_category,
    grade_schema_units_revenue_fields,
    grade_simulate_discount_wool_coat,
    grade_slowest_products_90d,
    grade_stockout_risk_top_critical,
    grade_supplier_top_by_spend,
)


class EvalHarnessTests(unittest.TestCase):
    def test_contains_number_near_handles_commas_and_tolerance(self):
        self.assertTrue(contains_number_near("Revenue was $15,845", 15845, 0))
        self.assertTrue(contains_number_near("Forecast is about 18 units", 18.3, 1.0))
        self.assertFalse(contains_number_near("Forecast is 12 units", 18.3, 1.0))

    @patch("app.eval_harness.query_one")
    def test_active_product_count_grader(self, query_one):
        query_one.return_value = {"count": 12}

        grade = grade_active_product_count("There are **12 active products**.")

        self.assertTrue(grade.passed)
        self.assertIn("12 active products", grade.expected)

    @patch("app.eval_harness.query_all")
    def test_slowest_products_grader_reports_missing_products(self, query_all):
        query_all.return_value = [
            {"product": "Wool Coat", "units": 9},
            {"product": "Cashmere Sweater", "units": 17},
            {"product": "Cotton Cardigan", "units": 17},
        ]

        grade = grade_slowest_products_90d("Wool Coat and Cashmere Sweater are slow.")

        self.assertFalse(grade.passed)
        self.assertIn("Cotton Cardigan", grade.details[0])

    def test_schema_sales_by_category_grader(self):
        grade = grade_schema_sales_by_category(
            "Use sale_order_line join sale_order on order_id, join product_product "
            "on product_id, product_template on product_tmpl_id, and product_category "
            "on categ_id."
        )

        self.assertTrue(grade.passed)

    def test_schema_units_revenue_fields_grader(self):
        grade = grade_schema_units_revenue_fields(
            "Units sold are product_uom_qty, revenue is product_uom_qty * price_unit, "
            "and the order date is date_order."
        )

        self.assertTrue(grade.passed)

    @patch("app.eval_harness.stockout_risk")
    def test_stockout_risk_grader_names_top_critical_product(self, mock_stockout_risk):
        mock_stockout_risk.return_value = {
            "rows": [
                {"product": "Parka Jacket", "urgency": "out_of_stock", "qty_on_hand": 0, "avg_daily_sales": 1.2},
                {"product": "Wool Coat", "urgency": "critical", "qty_on_hand": 3, "avg_daily_sales": 0.8},
            ]
        }

        grade = grade_stockout_risk_top_critical("Parka Jacket is completely out of stock and urgently needs replenishment.")

        self.assertTrue(grade.passed)
        self.assertIn("Parka Jacket", grade.expected)

    @patch("app.eval_harness.stockout_risk")
    def test_stockout_risk_grader_fails_when_product_missing(self, mock_stockout_risk):
        mock_stockout_risk.return_value = {
            "rows": [{"product": "Parka Jacket", "urgency": "critical"}]
        }

        grade = grade_stockout_risk_top_critical("We have some inventory concerns with the Wool Coat.")

        self.assertFalse(grade.passed)

    @patch("app.eval_harness.inventory_aging")
    def test_inventory_aging_grader_names_top_product(self, mock_inventory_aging):
        mock_inventory_aging.return_value = {
            "rows": [{"product": "Cashmere Sweater", "stock_value": 4800.0, "qty_on_hand": 40}]
        }

        grade = grade_inventory_aging_top_dead_stock("Cashmere Sweater has the highest dead-stock value at $4,800.")

        self.assertTrue(grade.passed)
        self.assertIn("Cashmere Sweater", grade.expected)

    @patch("app.eval_harness.inventory_aging")
    def test_inventory_aging_grader_passes_when_no_dead_stock(self, mock_inventory_aging):
        mock_inventory_aging.return_value = {"rows": []}

        grade = grade_inventory_aging_top_dead_stock("Good news! There is no dead stock — all items have been sold recently.")

        self.assertTrue(grade.passed)

    @patch("app.eval_harness.inventory_aging")
    def test_inventory_aging_grader_fails_when_no_dead_stock_not_acknowledged(self, mock_inventory_aging):
        mock_inventory_aging.return_value = {"rows": []}

        grade = grade_inventory_aging_top_dead_stock("Let me check the inventory for you.")

        self.assertFalse(grade.passed)

    @patch("app.eval_harness.margin_analysis")
    def test_margin_top_category_grader(self, mock_margin_analysis):
        mock_margin_analysis.return_value = {
            "rows": [
                {"name": "Outerwear", "gross_profit": 18500.0, "margin_pct": 62.0},
                {"name": "Knitwear", "gross_profit": 9200.0, "margin_pct": 55.0},
            ]
        }

        grade = grade_margin_top_category_gross_profit("Outerwear had the highest gross profit at $18,500.")

        self.assertTrue(grade.passed)
        self.assertIn("Outerwear", grade.expected)

    @patch("app.eval_harness.margin_analysis")
    def test_margin_top_category_grader_fails_when_wrong_category(self, mock_margin_analysis):
        mock_margin_analysis.return_value = {
            "rows": [{"name": "Outerwear", "gross_profit": 18500.0, "margin_pct": 62.0}]
        }

        grade = grade_margin_top_category_gross_profit("Knitwear was the top category.")

        self.assertFalse(grade.passed)

    @patch("app.eval_harness.supplier_scorecard")
    def test_supplier_top_grader_names_top_supplier(self, mock_supplier_scorecard):
        mock_supplier_scorecard.return_value = {
            "rows": [
                {"supplier": "Nordic Textiles AS", "total_spend": 52000.0, "fill_rate_pct": 97.5},
                {"supplier": "Alpaca Source Co", "total_spend": 31000.0, "fill_rate_pct": 88.0},
            ]
        }

        grade = grade_supplier_top_by_spend("Nordic Textiles AS was our top supplier with $52,000 in spend.")

        self.assertTrue(grade.passed)
        self.assertIn("Nordic Textiles AS", grade.expected)

    @patch("app.eval_harness.simulate_discount_impact")
    def test_simulate_discount_grader_passes_with_revenue_and_margin(self, mock_simulate):
        mock_simulate.return_value = {
            "products": [{
                "product": "Wool Coat",
                "simulated_revenue": 3840.0,
                "revenue_delta": -960.0,
                "simulated_price": 160.0,
                "baseline_revenue": 4800.0,
                "simulated_margin": 1440.0,
                "margin_delta": -360.0,
            }],
            "totals": {},
        }

        grade = grade_simulate_discount_wool_coat(
            "Wool Coat at 20% discount: simulated revenue $3,840 (delta -$960). Margin also drops."
        )

        self.assertTrue(grade.passed)

    @patch("app.eval_harness.simulate_discount_impact")
    def test_simulate_discount_grader_fails_without_financial_figure(self, mock_simulate):
        mock_simulate.return_value = {
            "products": [{
                "product": "Wool Coat",
                "simulated_revenue": 3840.0,
                "revenue_delta": -960.0,
                "simulated_price": 160.0,
                "baseline_revenue": 4800.0,
                "simulated_margin": 1440.0,
                "margin_delta": -360.0,
            }],
            "totals": {},
        }

        grade = grade_simulate_discount_wool_coat("Wool Coat will see a discount applied.")

        self.assertFalse(grade.passed)


if __name__ == "__main__":
    unittest.main()
