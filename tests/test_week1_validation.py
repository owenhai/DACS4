import unittest
from pathlib import Path

import duckdb

from src.data.eda import build_eda_report
from src.data.schema_metadata import (
    get_schema_description,
    get_schema_metadata,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "database" / "olist_analytics.duckdb"
EXPECTED_TABLES = {
    "fact_orders",
    "dim_customers",
    "dim_products",
    "dim_sellers",
    "dim_date",
    "dim_geolocation",
}


class Week1ValidationTests(unittest.TestCase):
    def test_database_contains_expected_tables(self):
        self.assertTrue(DATABASE_PATH.exists())
        with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
            tables = {
                row[0]
                for row in connection.execute("SHOW TABLES").fetchall()
            }
        self.assertEqual(tables, EXPECTED_TABLES)

    def test_fact_table_has_expected_rows_and_valid_dimension_keys(self):
        with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
            fact_count = connection.execute(
                "SELECT COUNT(*) FROM fact_orders"
            ).fetchone()[0]
            orphan_customers = connection.execute(
                """
                SELECT COUNT(*)
                FROM fact_orders AS fact
                LEFT JOIN dim_customers AS customer
                    ON fact.customer_key = customer.customer_key
                WHERE fact.customer_key IS NOT NULL
                  AND customer.customer_key IS NULL
                """
            ).fetchone()[0]
        self.assertEqual(fact_count, 112650)
        self.assertEqual(orphan_customers, 0)

    def test_metadata_matches_database_tables(self):
        metadata_tables = set(get_schema_metadata())
        self.assertEqual(metadata_tables, EXPECTED_TABLES)
        description = get_schema_description()
        self.assertIn("fact_orders", description)
        self.assertIn("RELATIONSHIPS", description)

    def test_raw_files_have_eda_summary_and_expected_row_counts(self):
        report = build_eda_report(str(PROJECT_ROOT / "data" / "raw"))
        self.assertEqual(len(report), 9)
        expected_rows = {
            "orders": 99441,
            "order_items": 112650,
            "customers": 99441,
            "products": 32951,
            "sellers": 3095,
            "payments": 103886,
            "reviews": 99224,
            "geolocation": 1000163,
            "category_translation": 71,
        }
        actual_rows = dict(zip(report["table"], report["rows"]))
        self.assertEqual(actual_rows, expected_rows)

    def test_fact_table_has_valid_dimension_keys_and_sample_queries(self):
        with duckdb.connect(str(DATABASE_PATH), read_only=True) as connection:
            orphan_counts = connection.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE customer_key IS NOT NULL
                        AND customer_key NOT IN (SELECT customer_key FROM dim_customers)),
                    COUNT(*) FILTER (WHERE product_key IS NOT NULL
                        AND product_key NOT IN (SELECT product_key FROM dim_products)),
                    COUNT(*) FILTER (WHERE seller_key IS NOT NULL
                        AND seller_key NOT IN (SELECT seller_key FROM dim_sellers)),
                    COUNT(*) FILTER (WHERE date_key IS NOT NULL
                        AND date_key NOT IN (SELECT date_key FROM dim_date))
                FROM fact_orders
                """
            ).fetchone()
            monthly_rows = connection.execute(
                """
                SELECT date.year, date.month, COUNT(*)
                FROM fact_orders AS fact
                JOIN dim_date AS date ON fact.date_key = date.date_key
                GROUP BY date.year, date.month
                ORDER BY date.year, date.month
                """
            ).fetchall()
            category_rows = connection.execute(
                """
                SELECT product.product_category_name_english, SUM(fact.price)
                FROM fact_orders AS fact
                JOIN dim_products AS product
                    ON fact.product_key = product.product_key
                GROUP BY product.product_category_name_english
                ORDER BY SUM(fact.price) DESC
                LIMIT 5
                """
            ).fetchall()

        self.assertEqual(orphan_counts, (0, 0, 0, 0))
        self.assertGreater(len(monthly_rows), 0)
        self.assertEqual(len(category_rows), 5)


if __name__ == "__main__":
    unittest.main()
