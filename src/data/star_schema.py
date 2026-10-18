"""Module thiết kế Star Schema và nạp dữ liệu vào DuckDB.

Star Schema bao gồm:
- fact_orders:    Bảng fact chứa thông tin đơn hàng tổng hợp
- dim_customers:  Dimension khách hàng
- dim_products:   Dimension sản phẩm
- dim_sellers:    Dimension người bán
- dim_date:       Dimension thời gian
- dim_geolocation: Dimension vị trí địa lý

Pipeline:
1. Đọc dữ liệu đã làm sạch (parquet) từ data/processed/
2. Tạo các bảng dimension với surrogate key
3. Tạo bảng fact bằng cách join tất cả dữ liệu
4. Nạp vào DuckDB
"""

import logging
from pathlib import Path

import duckdb
import pandas as pd

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQL DDL cho các bảng trong DuckDB
# ---------------------------------------------------------------------------

DDL_DIM_DATE = """
CREATE TABLE IF NOT EXISTS dim_date (
    date_key        INTEGER PRIMARY KEY,  -- YYYYMMDD
    full_date       DATE NOT NULL,
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    month_name      VARCHAR NOT NULL,
    day             INTEGER NOT NULL,
    day_of_week     INTEGER NOT NULL,     -- 0=Monday ... 6=Sunday
    day_name        VARCHAR NOT NULL,
    is_weekend      BOOLEAN NOT NULL
);
"""

DDL_DIM_CUSTOMERS = """
CREATE TABLE IF NOT EXISTS dim_customers (
    customer_key            INTEGER PRIMARY KEY,
    customer_id             VARCHAR NOT NULL,
    customer_unique_id      VARCHAR NOT NULL,
    customer_city           VARCHAR,
    customer_state          VARCHAR
);
"""

DDL_DIM_PRODUCTS = """
CREATE TABLE IF NOT EXISTS dim_products (
    product_key                  INTEGER PRIMARY KEY,
    product_id                   VARCHAR NOT NULL,
    product_category_name_english VARCHAR,
    product_name_length          DOUBLE,
    product_description_length   DOUBLE,
    product_photos_qty           DOUBLE,
    product_weight_g             DOUBLE,
    product_length_cm            DOUBLE,
    product_height_cm            DOUBLE,
    product_width_cm             DOUBLE
);
"""

DDL_DIM_SELLERS = """
CREATE TABLE IF NOT EXISTS dim_sellers (
    seller_key              INTEGER PRIMARY KEY,
    seller_id               VARCHAR NOT NULL,
    seller_city             VARCHAR,
    seller_state            VARCHAR,
    seller_zip_code_prefix  INTEGER
);
"""

DDL_DIM_GEOLOCATION = """
CREATE TABLE IF NOT EXISTS dim_geolocation (
    geolocation_zip_code_prefix  INTEGER PRIMARY KEY,
    geolocation_lat              DOUBLE,
    geolocation_lng              DOUBLE,
    geolocation_city             VARCHAR,
    geolocation_state            VARCHAR
);
"""

DDL_FACT_ORDERS = """
CREATE TABLE IF NOT EXISTS fact_orders (
    order_id        VARCHAR NOT NULL,
    customer_key    INTEGER,
    product_key     INTEGER,
    seller_key      INTEGER,
    date_key        INTEGER,
    order_status    VARCHAR,
    price           DOUBLE,
    freight_value   DOUBLE,
    payment_value   DOUBLE,
    payment_type    VARCHAR,
    review_score    DOUBLE,
    delivery_days   DOUBLE,
    FOREIGN KEY (customer_key) REFERENCES dim_customers(customer_key),
    FOREIGN KEY (product_key)  REFERENCES dim_products(product_key),
    FOREIGN KEY (seller_key)   REFERENCES dim_sellers(seller_key),
    FOREIGN KEY (date_key)     REFERENCES dim_date(date_key)
);
"""


# ---------------------------------------------------------------------------
# Tạo Dimension Tables
# ---------------------------------------------------------------------------

def create_dim_date(
    start_date: str = "2016-01-01",
    end_date: str = "2019-12-31",
) -> pd.DataFrame:
    """Tạo bảng dimension thời gian.

    Sinh tất cả các ngày trong khoảng [start_date, end_date]
    với các thuộc tính: year, quarter, month, day_of_week, v.v.

    Args:
        start_date: Ngày bắt đầu (YYYY-MM-DD).
        end_date: Ngày kết thúc (YYYY-MM-DD).

    Returns:
        DataFrame chứa bảng dim_date.
    """
    logger.info("Tạo dim_date từ %s đến %s...", start_date, end_date)

    dates = pd.date_range(start=start_date, end=end_date, freq="D")

    dim_date = pd.DataFrame(
        {
            "date_key": dates.strftime("%Y%m%d").astype(int),
            "full_date": dates.date,
            "year": dates.year,
            "quarter": dates.quarter,
            "month": dates.month,
            "month_name": dates.strftime("%B"),
            "day": dates.day,
            "day_of_week": dates.dayofweek,        # 0=Monday
            "day_name": dates.strftime("%A"),
            "is_weekend": dates.dayofweek >= 5,
        }
    )

    logger.info("  ✓ dim_date: %d dòng.", len(dim_date))
    return dim_date


def create_dim_customers(df_customers: pd.DataFrame) -> pd.DataFrame:
    """Tạo bảng dimension khách hàng với surrogate key.

    Args:
        df_customers: DataFrame khách hàng đã làm sạch.

    Returns:
        DataFrame chứa bảng dim_customers.
    """
    logger.info("Tạo dim_customers...")

    dim = df_customers[
        ["customer_id", "customer_unique_id", "customer_city", "customer_state"]
    ].copy()

    # Tạo surrogate key (bắt đầu từ 1)
    dim = dim.reset_index(drop=True)
    dim.insert(0, "customer_key", dim.index + 1)

    logger.info("  ✓ dim_customers: %d dòng.", len(dim))
    return dim


def create_dim_products(df_products: pd.DataFrame) -> pd.DataFrame:
    """Tạo bảng dimension sản phẩm với surrogate key.

    Args:
        df_products: DataFrame sản phẩm đã làm sạch.

    Returns:
        DataFrame chứa bảng dim_products.
    """
    logger.info("Tạo dim_products...")

    cols = [
        "product_id",
        "product_category_name_english",
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]
    # Chỉ lấy các cột tồn tại
    available_cols = [c for c in cols if c in df_products.columns]
    dim = df_products[available_cols].copy()

    dim = dim.reset_index(drop=True)
    dim.insert(0, "product_key", dim.index + 1)

    logger.info("  ✓ dim_products: %d dòng.", len(dim))
    return dim


def create_dim_sellers(df_sellers: pd.DataFrame) -> pd.DataFrame:
    """Tạo bảng dimension người bán với surrogate key.

    Args:
        df_sellers: DataFrame sellers đã làm sạch.

    Returns:
        DataFrame chứa bảng dim_sellers.
    """
    logger.info("Tạo dim_sellers...")

    dim = df_sellers[
        ["seller_id", "seller_city", "seller_state", "seller_zip_code_prefix"]
    ].copy()

    dim = dim.reset_index(drop=True)
    dim.insert(0, "seller_key", dim.index + 1)

    logger.info("  ✓ dim_sellers: %d dòng.", len(dim))
    return dim


# ---------------------------------------------------------------------------
# Tạo Fact Table
# ---------------------------------------------------------------------------

def create_fact_orders(
    df_orders: pd.DataFrame,
    df_items: pd.DataFrame,
    df_payments: pd.DataFrame,
    df_reviews: pd.DataFrame,
    dim_customers: pd.DataFrame,
    dim_products: pd.DataFrame,
    dim_sellers: pd.DataFrame,
    dim_date: pd.DataFrame,
) -> pd.DataFrame:
    """Tạo bảng fact_orders bằng cách join tất cả dữ liệu.

    Bảng fact ở mức grain: 1 dòng = 1 order_item (sản phẩm trong đơn hàng).

    Tính toán:
    - delivery_days = (delivered_date - purchase_date).days
    - payment_value: tổng thanh toán của đơn hàng
    - review_score: điểm đánh giá (nếu có)

    Args:
        df_orders: Bảng orders đã làm sạch.
        df_items: Bảng order_items đã làm sạch.
        df_payments: Bảng payments đã làm sạch.
        df_reviews: Bảng reviews đã làm sạch.
        dim_customers: Bảng dim_customers (có surrogate key).
        dim_products: Bảng dim_products (có surrogate key).
        dim_sellers: Bảng dim_sellers (có surrogate key).
        dim_date: Bảng dim_date.

    Returns:
        DataFrame chứa bảng fact_orders.
    """
    logger.info("Tạo fact_orders...")

    # --- Bước 1: Tổng hợp payments theo order ---
    # Lấy payment chính (giá trị lớn nhất) cho payment_type
    payments_agg = (
        df_payments.groupby("order_id")
        .agg(
            payment_value=("payment_value", "sum"),
            payment_type=("payment_type", "first"),  # Loại thanh toán chính
        )
        .reset_index()
    )

    # --- Bước 2: Lấy review score theo order ---
    reviews_simple = df_reviews[["order_id", "review_score"]].copy()

    # --- Bước 3: Join order_items với orders ---
    fact = df_items[
        ["order_id", "product_id", "seller_id", "price", "freight_value"]
    ].merge(
        df_orders[
            [
                "order_id",
                "customer_id",
                "order_status",
                "order_purchase_timestamp",
                "order_delivered_customer_date",
            ]
        ],
        on="order_id",
        how="left",
    )

    # --- Bước 4: Join payments và reviews ---
    fact = fact.merge(payments_agg, on="order_id", how="left")
    fact = fact.merge(reviews_simple, on="order_id", how="left")

    # --- Bước 5: Tính delivery_days ---
    fact["delivery_days"] = (
        fact["order_delivered_customer_date"]
        - fact["order_purchase_timestamp"]
    ).dt.days
    # Delivery days < 0 hoặc NaN → giữ NaN
    fact.loc[fact["delivery_days"] < 0, "delivery_days"] = None

    # --- Bước 6: Tạo date_key từ order_purchase_timestamp ---
    fact["date_key"] = (
        fact["order_purchase_timestamp"]
        .dt.strftime("%Y%m%d")
        .astype(float)
        .astype("Int64")
    )

    # --- Bước 7: Map surrogate keys ---
    # Customer key
    customer_map = dict(
        zip(dim_customers["customer_id"], dim_customers["customer_key"])
    )
    fact["customer_key"] = fact["customer_id"].map(customer_map)

    # Product key
    product_map = dict(
        zip(dim_products["product_id"], dim_products["product_key"])
    )
    fact["product_key"] = fact["product_id"].map(product_map)

    # Seller key
    seller_map = dict(
        zip(dim_sellers["seller_id"], dim_sellers["seller_key"])
    )
    fact["seller_key"] = fact["seller_id"].map(seller_map)

    # --- Bước 8: Validate date_key tồn tại trong dim_date ---
    valid_dates = set(dim_date["date_key"])
    invalid_dates = fact[~fact["date_key"].isin(valid_dates) & fact["date_key"].notna()]
    if len(invalid_dates) > 0:
        logger.warning(
            "  ⚠ %d dòng có date_key không nằm trong dim_date.", len(invalid_dates)
        )

    # --- Bước 9: Chọn cột cuối cùng ---
    fact_final = fact[
        [
            "order_id",
            "customer_key",
            "product_key",
            "seller_key",
            "date_key",
            "order_status",
            "price",
            "freight_value",
            "payment_value",
            "payment_type",
            "review_score",
            "delivery_days",
        ]
    ].copy()

    # Chuyển đổi kiểu dữ liệu
    for col in ["customer_key", "product_key", "seller_key", "date_key"]:
        fact_final[col] = fact_final[col].astype("Int64")

    logger.info("  ✓ fact_orders: %d dòng.", len(fact_final))
    return fact_final


# ---------------------------------------------------------------------------
# Nạp vào DuckDB
# ---------------------------------------------------------------------------

def load_star_schema_to_duckdb(
    db_path: str,
    fact_df: pd.DataFrame,
    dim_dfs: dict[str, pd.DataFrame],
) -> None:
    """Tạo bảng và nạp dữ liệu Star Schema vào DuckDB.

    Args:
        db_path: Đường dẫn file DuckDB (vd: data/olist.duckdb).
        fact_df: DataFrame bảng fact_orders.
        dim_dfs: Dictionary {tên_bảng: DataFrame} cho các bảng dimension.

    Raises:
        RuntimeError: Khi nạp dữ liệu thất bại.
    """
    logger.info("Nạp Star Schema vào DuckDB: %s", db_path)

    # Đảm bảo thư mục tồn tại
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        con = duckdb.connect(db_path)

        # Tạo và nạp các bảng dimension trước (do FK constraints)
        ddl_map = {
            "dim_date": DDL_DIM_DATE,
            "dim_customers": DDL_DIM_CUSTOMERS,
            "dim_products": DDL_DIM_PRODUCTS,
            "dim_sellers": DDL_DIM_SELLERS,
            "dim_geolocation": DDL_DIM_GEOLOCATION,
        }

        for table_name, ddl in ddl_map.items():
            if table_name in dim_dfs:
                # Drop bảng cũ nếu tồn tại rồi tạo lại
                con.execute(f"DROP TABLE IF EXISTS {table_name}")
                con.execute(ddl)

                df = dim_dfs[table_name]
                con.execute(
                    f"INSERT INTO {table_name} SELECT * FROM df"
                )
                count = con.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                logger.info("  ✓ %s: %d rows loaded.", table_name, count)

        # Tạo và nạp bảng fact
        con.execute("DROP TABLE IF EXISTS fact_orders")
        con.execute(DDL_FACT_ORDERS)
        con.execute("INSERT INTO fact_orders SELECT * FROM fact_df")
        fact_count = con.execute(
            "SELECT COUNT(*) FROM fact_orders"
        ).fetchone()[0]
        logger.info("  ✓ fact_orders: %d rows loaded.", fact_count)

        # Kiểm tra tổng quan
        tables = con.execute("SHOW TABLES").fetchall()
        logger.info("  📋 Các bảng trong DB: %s", [t[0] for t in tables])

        con.close()
        logger.info("✅ Đã nạp Star Schema vào %s thành công!", db_path)

    except Exception as exc:
        logger.error("Lỗi khi nạp vào DuckDB: %s", exc)
        raise RuntimeError(f"Nạp DuckDB thất bại: {exc}") from exc


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def build_star_schema(
    processed_dir: str = "data/processed",
    db_path: str = "data/olist.duckdb",
) -> None:
    """Orchestrator: đọc dữ liệu đã xử lý, xây dựng Star Schema, nạp DuckDB.

    Args:
        processed_dir: Thư mục chứa file parquet đã làm sạch.
        db_path: Đường dẫn file DuckDB đích.
    """
    logger.info("=" * 60)
    logger.info("BẮT ĐẦU XÂY DỰNG STAR SCHEMA")
    logger.info("=" * 60)

    proc = Path(processed_dir)

    # --- Đọc dữ liệu đã xử lý ---
    try:
        df_orders = pd.read_parquet(proc / "orders.parquet")
        df_items = pd.read_parquet(proc / "order_items.parquet")
        df_customers = pd.read_parquet(proc / "customers.parquet")
        df_products = pd.read_parquet(proc / "products.parquet")
        df_sellers = pd.read_parquet(proc / "sellers.parquet")
        df_payments = pd.read_parquet(proc / "payments.parquet")
        df_reviews = pd.read_parquet(proc / "reviews.parquet")
        df_geolocation = pd.read_parquet(proc / "geolocation.parquet")
    except FileNotFoundError as exc:
        logger.error("Thiếu file parquet: %s", exc)
        raise

    logger.info("Đã đọc tất cả dữ liệu processed.")

    # --- Tạo Dimension Tables ---
    dim_date = create_dim_date("2016-01-01", "2019-12-31")
    dim_customers = create_dim_customers(df_customers)
    dim_products = create_dim_products(df_products)
    dim_sellers = create_dim_sellers(df_sellers)

    # Geolocation dimension (đã deduplicate sẵn)
    dim_geolocation = df_geolocation[
        [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ]
    ].copy()

    # --- Tạo Fact Table ---
    fact_orders = create_fact_orders(
        df_orders=df_orders,
        df_items=df_items,
        df_payments=df_payments,
        df_reviews=df_reviews,
        dim_customers=dim_customers,
        dim_products=dim_products,
        dim_sellers=dim_sellers,
        dim_date=dim_date,
    )

    # --- Nạp vào DuckDB ---
    dim_dfs = {
        "dim_date": dim_date,
        "dim_customers": dim_customers,
        "dim_products": dim_products,
        "dim_sellers": dim_sellers,
        "dim_geolocation": dim_geolocation,
    }

    load_star_schema_to_duckdb(db_path, fact_orders, dim_dfs)

    logger.info("=" * 60)
    logger.info("✅ HOÀN TẤT XÂY DỰNG STAR SCHEMA")
    logger.info("=" * 60)


if __name__ == "__main__":
    build_star_schema()
