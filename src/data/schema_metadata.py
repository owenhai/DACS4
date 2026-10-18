"""Module metadata schema cho pipeline Text-to-SQL.

Cung cấp thông tin chi tiết về cấu trúc Star Schema (bảng, cột, kiểu dữ liệu,
quan hệ FK, giá trị mẫu) để LLM có thể sinh câu SQL chính xác.

Sử dụng trong Week 2 khi xây dựng Text-to-SQL pipeline với Gemini.
"""

import logging
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema Metadata Dictionary
# ---------------------------------------------------------------------------

SCHEMA_METADATA: dict[str, Any] = {
    # ==================================================================
    # FACT TABLE
    # ==================================================================
    "fact_orders": {
        "description": (
            "Fact table containing order-level transactional data. "
            "Each row represents one item in an order, linked to customer, "
            "product, seller, and date dimensions. Contains measures like "
            "price, freight value, payment value, review score, and "
            "calculated delivery days."
        ),
        "grain": "One row per order item (product within an order)",
        "columns": {
            "order_id": {
                "type": "VARCHAR",
                "description": "Unique identifier for the order",
                "is_key": False,
                "nullable": False,
            },
            "customer_key": {
                "type": "INTEGER",
                "description": "Surrogate key linking to dim_customers",
                "is_key": True,
                "nullable": True,
                "references": "dim_customers.customer_key",
            },
            "product_key": {
                "type": "INTEGER",
                "description": "Surrogate key linking to dim_products",
                "is_key": True,
                "nullable": True,
                "references": "dim_products.product_key",
            },
            "seller_key": {
                "type": "INTEGER",
                "description": "Surrogate key linking to dim_sellers",
                "is_key": True,
                "nullable": True,
                "references": "dim_sellers.seller_key",
            },
            "date_key": {
                "type": "INTEGER",
                "description": (
                    "Date key in YYYYMMDD format linking to dim_date. "
                    "Represents the order purchase date."
                ),
                "is_key": True,
                "nullable": True,
                "references": "dim_date.date_key",
            },
            "order_status": {
                "type": "VARCHAR",
                "description": "Current status of the order",
                "is_key": False,
                "nullable": True,
                "sample_values": [
                    "delivered",
                    "shipped",
                    "canceled",
                    "unavailable",
                    "invoiced",
                    "processing",
                    "created",
                    "approved",
                ],
            },
            "price": {
                "type": "DOUBLE",
                "description": "Product price in BRL (Brazilian Real)",
                "is_key": False,
                "nullable": True,
            },
            "freight_value": {
                "type": "DOUBLE",
                "description": "Shipping/freight cost in BRL",
                "is_key": False,
                "nullable": True,
            },
            "payment_value": {
                "type": "DOUBLE",
                "description": (
                    "Total payment value for the order in BRL "
                    "(sum of all payment installments)"
                ),
                "is_key": False,
                "nullable": True,
            },
            "payment_type": {
                "type": "VARCHAR",
                "description": "Primary payment method used",
                "is_key": False,
                "nullable": True,
                "sample_values": [
                    "credit_card",
                    "boleto",
                    "voucher",
                    "debit_card",
                ],
            },
            "review_score": {
                "type": "DOUBLE",
                "description": "Customer review score from 1 (worst) to 5 (best)",
                "is_key": False,
                "nullable": True,
                "sample_values": [1, 2, 3, 4, 5],
            },
            "delivery_days": {
                "type": "DOUBLE",
                "description": (
                    "Number of days between order purchase and delivery. "
                    "NULL if not yet delivered."
                ),
                "is_key": False,
                "nullable": True,
            },
        },
    },

    # ==================================================================
    # DIMENSION: CUSTOMERS
    # ==================================================================
    "dim_customers": {
        "description": (
            "Customer dimension table. Contains customer demographic and "
            "geographic information. Each row represents a unique customer "
            "identified by customer_id."
        ),
        "columns": {
            "customer_key": {
                "type": "INTEGER",
                "description": "Surrogate primary key",
                "is_key": True,
                "nullable": False,
            },
            "customer_id": {
                "type": "VARCHAR",
                "description": (
                    "Original customer ID linked to orders. "
                    "One customer_unique_id can have multiple customer_ids."
                ),
                "is_key": False,
                "nullable": False,
            },
            "customer_unique_id": {
                "type": "VARCHAR",
                "description": (
                    "Unique identifier for the person. A person can place "
                    "multiple orders with different customer_ids."
                ),
                "is_key": False,
                "nullable": False,
            },
            "customer_city": {
                "type": "VARCHAR",
                "description": "City where the customer is located (Title Case)",
                "is_key": False,
                "nullable": True,
                "sample_values": [
                    "Sao Paulo",
                    "Rio De Janeiro",
                    "Belo Horizonte",
                    "Brasilia",
                    "Curitiba",
                ],
            },
            "customer_state": {
                "type": "VARCHAR",
                "description": "Brazilian state abbreviation (uppercase, 2 letters)",
                "is_key": False,
                "nullable": True,
                "sample_values": ["SP", "RJ", "MG", "RS", "PR", "BA", "SC", "DF"],
            },
        },
    },

    # ==================================================================
    # DIMENSION: PRODUCTS
    # ==================================================================
    "dim_products": {
        "description": (
            "Product dimension table. Contains product attributes including "
            "category (translated to English), physical dimensions, and weight."
        ),
        "columns": {
            "product_key": {
                "type": "INTEGER",
                "description": "Surrogate primary key",
                "is_key": True,
                "nullable": False,
            },
            "product_id": {
                "type": "VARCHAR",
                "description": "Original product identifier",
                "is_key": False,
                "nullable": False,
            },
            "product_category_name_english": {
                "type": "VARCHAR",
                "description": (
                    "Product category name translated to English. "
                    "Examples include electronics, furniture, beauty products."
                ),
                "is_key": False,
                "nullable": True,
                "sample_values": [
                    "bed_bath_table",
                    "health_beauty",
                    "sports_leisure",
                    "furniture_decor",
                    "computers_accessories",
                    "housewares",
                    "watches_gifts",
                    "telephony",
                    "auto",
                    "toys",
                    "cool_stuff",
                    "garden_tools",
                    "baby",
                    "perfumery",
                    "stationery",
                ],
            },
            "product_name_length": {
                "type": "DOUBLE",
                "description": "Number of characters in the product name",
                "is_key": False,
                "nullable": True,
            },
            "product_description_length": {
                "type": "DOUBLE",
                "description": "Number of characters in the product description",
                "is_key": False,
                "nullable": True,
            },
            "product_photos_qty": {
                "type": "DOUBLE",
                "description": "Number of product photos published",
                "is_key": False,
                "nullable": True,
            },
            "product_weight_g": {
                "type": "DOUBLE",
                "description": "Product weight in grams",
                "is_key": False,
                "nullable": True,
            },
            "product_length_cm": {
                "type": "DOUBLE",
                "description": "Product length in centimeters",
                "is_key": False,
                "nullable": True,
            },
            "product_height_cm": {
                "type": "DOUBLE",
                "description": "Product height in centimeters",
                "is_key": False,
                "nullable": True,
            },
            "product_width_cm": {
                "type": "DOUBLE",
                "description": "Product width in centimeters",
                "is_key": False,
                "nullable": True,
            },
        },
    },

    # ==================================================================
    # DIMENSION: SELLERS
    # ==================================================================
    "dim_sellers": {
        "description": (
            "Seller dimension table. Contains seller geographic information."
        ),
        "columns": {
            "seller_key": {
                "type": "INTEGER",
                "description": "Surrogate primary key",
                "is_key": True,
                "nullable": False,
            },
            "seller_id": {
                "type": "VARCHAR",
                "description": "Original seller identifier",
                "is_key": False,
                "nullable": False,
            },
            "seller_city": {
                "type": "VARCHAR",
                "description": "City where the seller is located (Title Case)",
                "is_key": False,
                "nullable": True,
                "sample_values": [
                    "Sao Paulo",
                    "Curitiba",
                    "Rio De Janeiro",
                    "Belo Horizonte",
                    "Ribeirao Preto",
                ],
            },
            "seller_state": {
                "type": "VARCHAR",
                "description": "Brazilian state abbreviation (uppercase, 2 letters)",
                "is_key": False,
                "nullable": True,
                "sample_values": ["SP", "PR", "MG", "RJ", "SC", "RS", "BA"],
            },
            "seller_zip_code_prefix": {
                "type": "INTEGER",
                "description": "First 5 digits of seller zip code",
                "is_key": False,
                "nullable": True,
            },
        },
    },

    # ==================================================================
    # DIMENSION: DATE
    # ==================================================================
    "dim_date": {
        "description": (
            "Date dimension table. Contains calendar attributes for each day "
            "from 2016-01-01 to 2019-12-31. Used to analyze orders by time "
            "periods (year, quarter, month, day of week)."
        ),
        "columns": {
            "date_key": {
                "type": "INTEGER",
                "description": (
                    "Primary key in YYYYMMDD integer format. "
                    "Example: 20170815 for August 15, 2017."
                ),
                "is_key": True,
                "nullable": False,
            },
            "full_date": {
                "type": "DATE",
                "description": "Full calendar date",
                "is_key": False,
                "nullable": False,
            },
            "year": {
                "type": "INTEGER",
                "description": "Calendar year (2016-2019)",
                "is_key": False,
                "nullable": False,
                "sample_values": [2016, 2017, 2018, 2019],
            },
            "quarter": {
                "type": "INTEGER",
                "description": "Calendar quarter (1-4)",
                "is_key": False,
                "nullable": False,
                "sample_values": [1, 2, 3, 4],
            },
            "month": {
                "type": "INTEGER",
                "description": "Calendar month (1-12)",
                "is_key": False,
                "nullable": False,
                "sample_values": list(range(1, 13)),
            },
            "month_name": {
                "type": "VARCHAR",
                "description": "Full month name in English",
                "is_key": False,
                "nullable": False,
                "sample_values": [
                    "January", "February", "March", "April",
                    "May", "June", "July", "August",
                    "September", "October", "November", "December",
                ],
            },
            "day": {
                "type": "INTEGER",
                "description": "Day of month (1-31)",
                "is_key": False,
                "nullable": False,
            },
            "day_of_week": {
                "type": "INTEGER",
                "description": "Day of week as integer (0=Monday, 6=Sunday)",
                "is_key": False,
                "nullable": False,
                "sample_values": [0, 1, 2, 3, 4, 5, 6],
            },
            "day_name": {
                "type": "VARCHAR",
                "description": "Full day name in English",
                "is_key": False,
                "nullable": False,
                "sample_values": [
                    "Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday",
                ],
            },
            "is_weekend": {
                "type": "BOOLEAN",
                "description": "True if Saturday or Sunday",
                "is_key": False,
                "nullable": False,
                "sample_values": [True, False],
            },
        },
    },

    # ==================================================================
    # DIMENSION: GEOLOCATION
    # ==================================================================
    "dim_geolocation": {
        "description": (
            "Geolocation dimension table. Contains geographic coordinates "
            "(latitude/longitude) for Brazilian zip code prefixes. "
            "Can be joined with customers or sellers via zip_code_prefix."
        ),
        "columns": {
            "geolocation_zip_code_prefix": {
                "type": "INTEGER",
                "description": "First 5 digits of Brazilian zip code (primary key)",
                "is_key": True,
                "nullable": False,
            },
            "geolocation_lat": {
                "type": "DOUBLE",
                "description": "Latitude coordinate",
                "is_key": False,
                "nullable": True,
            },
            "geolocation_lng": {
                "type": "DOUBLE",
                "description": "Longitude coordinate",
                "is_key": False,
                "nullable": True,
            },
            "geolocation_city": {
                "type": "VARCHAR",
                "description": "City name (Title Case)",
                "is_key": False,
                "nullable": True,
            },
            "geolocation_state": {
                "type": "VARCHAR",
                "description": "Brazilian state abbreviation (uppercase, 2 letters)",
                "is_key": False,
                "nullable": True,
                "sample_values": ["SP", "RJ", "MG", "RS", "PR", "BA"],
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Quan hệ khoá ngoại (Foreign Key Relationships)
# ---------------------------------------------------------------------------

TABLE_RELATIONSHIPS: list[dict[str, str]] = [
    {
        "from_table": "fact_orders",
        "from_column": "customer_key",
        "to_table": "dim_customers",
        "to_column": "customer_key",
        "relationship": "Many-to-One",
        "description": "Each order item belongs to one customer",
    },
    {
        "from_table": "fact_orders",
        "from_column": "product_key",
        "to_table": "dim_products",
        "to_column": "product_key",
        "relationship": "Many-to-One",
        "description": "Each order item contains one product",
    },
    {
        "from_table": "fact_orders",
        "from_column": "seller_key",
        "to_table": "dim_sellers",
        "to_column": "seller_key",
        "relationship": "Many-to-One",
        "description": "Each order item is sold by one seller",
    },
    {
        "from_table": "fact_orders",
        "from_column": "date_key",
        "to_table": "dim_date",
        "to_column": "date_key",
        "relationship": "Many-to-One",
        "description": "Each order item has one purchase date",
    },
]


# ---------------------------------------------------------------------------
# Business Context (ngữ cảnh kinh doanh cho LLM)
# ---------------------------------------------------------------------------

BUSINESS_CONTEXT: str = """
This is the Olist Brazilian E-Commerce dataset, containing real (anonymized)
commercial data from the Olist marketplace in Brazil from 2016 to 2018.

Key business facts:
- Currency: Brazilian Real (BRL)
- Geography: All orders are from Brazil, with state codes like SP (São Paulo),
  RJ (Rio de Janeiro), MG (Minas Gerais), etc.
- Order lifecycle: created → approved → invoiced → shipped → delivered
- Delivery days: calculated as (delivery_date - purchase_date) in days
- Payment types: credit_card, boleto (bank slip), voucher, debit_card
- Review scores: 1 (worst) to 5 (best)
- Most orders were placed between 2017 and 2018
- The marketplace connects sellers across Brazil to customers

Common analysis patterns:
- Revenue analysis: SUM(price), SUM(freight_value), SUM(payment_value)
- Order volume: COUNT(DISTINCT order_id)
- Customer satisfaction: AVG(review_score)
- Delivery performance: AVG(delivery_days)
- Geographic analysis: GROUP BY customer_state or seller_state
- Time trends: GROUP BY year, month or quarter using dim_date
- Product category analysis: GROUP BY product_category_name_english
"""


# ---------------------------------------------------------------------------
# Hàm truy xuất metadata
# ---------------------------------------------------------------------------

def get_schema_metadata() -> dict[str, Any]:
    """Trả về dictionary metadata đầy đủ của Star Schema.

    Returns:
        Dictionary chứa thông tin tất cả bảng, cột, kiểu dữ liệu.
    """
    return SCHEMA_METADATA


def get_table_relationships() -> list[dict[str, str]]:
    """Trả về danh sách quan hệ khoá ngoại giữa các bảng.

    Returns:
        List các dict mô tả FK relationships.
    """
    return TABLE_RELATIONSHIPS


def format_schema_for_prompt() -> str:
    """Format metadata schema thành chuỗi text dễ đọc cho LLM prompt.

    Định dạng output bao gồm:
    - Business context
    - Mô tả từng bảng và các cột
    - Quan hệ FK
    - Giá trị mẫu cho các cột categorical

    Returns:
        Chuỗi text mô tả schema, sẵn sàng đưa vào prompt cho LLM.
    """
    lines: list[str] = []

    # --- Business Context ---
    lines.append("=" * 60)
    lines.append("DATABASE SCHEMA: Olist Brazilian E-Commerce (Star Schema)")
    lines.append("=" * 60)
    lines.append("")
    lines.append("BUSINESS CONTEXT:")
    lines.append(BUSINESS_CONTEXT.strip())
    lines.append("")

    # --- Table Descriptions ---
    lines.append("-" * 60)
    lines.append("TABLES AND COLUMNS:")
    lines.append("-" * 60)

    for table_name, table_info in SCHEMA_METADATA.items():
        lines.append("")
        lines.append(f"### {table_name}")
        lines.append(f"Description: {table_info['description']}")

        if "grain" in table_info:
            lines.append(f"Grain: {table_info['grain']}")

        lines.append("")
        lines.append(f"{'Column':<40} {'Type':<12} {'Description'}")
        lines.append(f"{'─' * 40} {'─' * 12} {'─' * 50}")

        for col_name, col_info in table_info["columns"].items():
            key_marker = " (PK)" if col_info.get("is_key") else ""
            fk_marker = ""
            if "references" in col_info:
                fk_marker = f" → {col_info['references']}"

            lines.append(
                f"{col_name:<40} {col_info['type']:<12} "
                f"{col_info['description']}{key_marker}{fk_marker}"
            )

            # Hiển thị giá trị mẫu (nếu có)
            if "sample_values" in col_info:
                samples = col_info["sample_values"]
                sample_str = ", ".join(str(v) for v in samples[:8])
                if len(samples) > 8:
                    sample_str += ", ..."
                lines.append(f"{'':>40} {'':>12} Sample values: [{sample_str}]")

    # --- Relationships ---
    lines.append("")
    lines.append("-" * 60)
    lines.append("RELATIONSHIPS (Foreign Keys):")
    lines.append("-" * 60)

    for rel in TABLE_RELATIONSHIPS:
        lines.append(
            f"  {rel['from_table']}.{rel['from_column']} "
            f"→ {rel['to_table']}.{rel['to_column']} "
            f"({rel['relationship']}): {rel['description']}"
        )

    # --- Join examples ---
    lines.append("")
    lines.append("-" * 60)
    lines.append("COMMON JOIN PATTERNS:")
    lines.append("-" * 60)
    lines.append("""
-- Revenue by customer state:
SELECT c.customer_state, SUM(f.price) AS total_revenue
FROM fact_orders f
JOIN dim_customers c ON f.customer_key = c.customer_key
GROUP BY c.customer_state
ORDER BY total_revenue DESC;

-- Monthly order count:
SELECT d.year, d.month, d.month_name, COUNT(DISTINCT f.order_id) AS order_count
FROM fact_orders f
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- Average review score by product category:
SELECT p.product_category_name_english, AVG(f.review_score) AS avg_score
FROM fact_orders f
JOIN dim_products p ON f.product_key = p.product_key
WHERE f.review_score IS NOT NULL
GROUP BY p.product_category_name_english
ORDER BY avg_score DESC;

-- Top sellers by revenue:
SELECT s.seller_city, s.seller_state, SUM(f.price) AS total_revenue
FROM fact_orders f
JOIN dim_sellers s ON f.seller_key = s.seller_key
GROUP BY s.seller_city, s.seller_state
ORDER BY total_revenue DESC
LIMIT 10;
""".strip())

    return "\n".join(lines)


def get_schema_description() -> str:
    """Return the formatted schema description for LLM prompts."""
    return format_schema_for_prompt()


if __name__ == "__main__":
    # In schema để kiểm tra
    schema_text = format_schema_for_prompt()
    print(schema_text)

    # In thống kê
    print("\n" + "=" * 60)
    print("THỐNG KÊ SCHEMA:")
    meta = get_schema_metadata()
    for table_name, table_info in meta.items():
        col_count = len(table_info["columns"])
        print(f"  {table_name}: {col_count} columns")

    print(f"\n  Relationships: {len(get_table_relationships())}")
