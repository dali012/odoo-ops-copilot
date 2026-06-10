import unittest
from unittest.mock import patch

from app.eval_harness import (
    contains_number_near,
    grade_active_product_count,
    grade_schema_sales_by_category,
    grade_schema_units_revenue_fields,
    grade_slowest_products_90d,
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


if __name__ == "__main__":
    unittest.main()
