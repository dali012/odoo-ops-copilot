import unittest

from app.tools import SQL_ROW_CAP, cap_sql, extract_sql_tables, sql_analytics, validate_sql


class SqlGuardrailTests(unittest.TestCase):
    def test_extracts_joined_odoo_tables(self):
        tables = extract_sql_tables(
            """
            SELECT pc.name, SUM(sol.product_uom_qty)
            FROM sale_order_line sol
            JOIN sale_order so ON so.id = sol.order_id
            JOIN product_product pp ON pp.id = sol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_category pc ON pc.id = pt.categ_id
            GROUP BY pc.name
            """
        )

        self.assertEqual(
            tables,
            {
                "sale_order_line",
                "sale_order",
                "product_product",
                "product_template",
                "product_category",
            },
        )

    def test_rejects_non_select_statement(self):
        with self.assertRaisesRegex(ValueError, "Only SELECT"):
            validate_sql("DELETE FROM sale_order")

    def test_rejects_multiple_statements(self):
        with self.assertRaisesRegex(ValueError, "single SELECT"):
            validate_sql("SELECT * FROM sale_order; SELECT * FROM product_template")

    def test_rejects_non_allowlisted_table(self):
        with self.assertRaisesRegex(ValueError, "non-allowlisted"):
            validate_sql("SELECT * FROM information_schema.tables")

    def test_allows_cte_alias_when_underlying_tables_are_allowed(self):
        validated = validate_sql(
            """
            WITH recent AS (
                SELECT * FROM sale_order_line
            )
            SELECT COUNT(*) FROM recent
            """
        )

        self.assertIn("recent", validated)

    def test_caps_rows_by_wrapping_query(self):
        capped = cap_sql("SELECT * FROM product_template")

        self.assertEqual(
            capped,
            f"SELECT * FROM (SELECT * FROM product_template) AS guarded_query LIMIT {SQL_ROW_CAP}",
        )

    def test_live_query_applies_row_cap(self):
        result = sql_analytics("SELECT * FROM sale_order_line ORDER BY id")

        self.assertLessEqual(result["row_count"], SQL_ROW_CAP)
        self.assertEqual(result["row_cap"], SQL_ROW_CAP)


if __name__ == "__main__":
    unittest.main()
