import unittest
from pathlib import Path

import duckdb

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


if __name__ == "__main__":
    unittest.main()
