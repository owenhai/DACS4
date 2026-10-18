"""Module làm sạch và tiền xử lý dữ liệu Olist Brazilian E-Commerce.

Pipeline xử lý:
1. Load tất cả file CSV thô từ data/raw
2. Làm sạch từng bảng: xử lý missing, chuẩn hoá kiểu dữ liệu, loại bỏ trùng lặp
3. Dịch tên danh mục sản phẩm từ tiếng Bồ Đào Nha sang tiếng Anh
4. Lưu kết quả dưới dạng Parquet vào data/processed/
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Mapping tên file CSV -> tên logic
CSV_FILE_MAP: dict[str, str] = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Các cột ngày tháng trong bảng orders
ORDER_DATE_COLUMNS: list[str] = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


# ---------------------------------------------------------------------------
# Hàm load dữ liệu thô
# ---------------------------------------------------------------------------

def load_raw_data(raw_dir: str = "data/raw") -> dict[str, pd.DataFrame]:
    """Load tất cả file CSV thô vào dict các DataFrame.

    Args:
        raw_dir: Đường dẫn thư mục chứa file CSV thô.

    Returns:
        Dictionary {tên_logic: DataFrame} cho từng bảng.

    Raises:
        FileNotFoundError: Khi thư mục hoặc file CSV không tồn tại.
    """
    raw_path = Path(raw_dir)
    if not raw_path.exists():
        raise FileNotFoundError(f"Thư mục dữ liệu thô không tồn tại: {raw_path}")

    dataframes: dict[str, pd.DataFrame] = {}

    for name, filename in CSV_FILE_MAP.items():
        filepath = raw_path / filename
        if not filepath.exists():
            logger.warning("Không tìm thấy file: %s", filepath)
            continue

        try:
            df = pd.read_csv(filepath)
            dataframes[name] = df
            logger.info(
                "  ✓ Loaded %-25s → %d rows × %d cols",
                filename,
                len(df),
                len(df.columns),
            )
        except Exception as exc:
            logger.error("Lỗi khi đọc file %s: %s", filename, exc)
            raise

    logger.info("Đã load %d/%d bảng dữ liệu.", len(dataframes), len(CSV_FILE_MAP))
    return dataframes


# ---------------------------------------------------------------------------
# Hàm làm sạch từng bảng
# ---------------------------------------------------------------------------

def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch bảng orders.

    Xử lý:
    - Parse các cột ngày tháng sang datetime
    - Xử lý missing delivery dates (đơn chưa giao)
    - Chuẩn hoá ID sang kiểu string
    - Loại bỏ bản ghi trùng lặp

    Args:
        df: DataFrame thô của bảng orders.

    Returns:
        DataFrame đã làm sạch.
    """
    logger.info("Đang làm sạch bảng orders (%d dòng)...", len(df))
    df = df.copy()

    # Chuẩn hoá ID sang string
    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["customer_id"] = df["customer_id"].astype(str).str.strip()

    # Parse các cột ngày tháng
    for col in ORDER_DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Xử lý missing delivery dates: chỉ đơn đã giao mới cần có delivery date
    # Đơn chưa giao (status != 'delivered') → giữ NaT
    delivered_mask = df["order_status"] == "delivered"
    missing_delivery = delivered_mask & df["order_delivered_customer_date"].isna()
    if missing_delivery.sum() > 0:
        logger.warning(
            "  ⚠ %d đơn 'delivered' thiếu ngày giao → dùng estimated date",
            missing_delivery.sum(),
        )
        df.loc[missing_delivery, "order_delivered_customer_date"] = df.loc[
            missing_delivery, "order_estimated_delivery_date"
        ]

    # Loại bỏ trùng lặp theo order_id
    before = len(df)
    df = df.drop_duplicates(subset=["order_id"], keep="first")
    if len(df) < before:
        logger.info("  Đã loại %d bản ghi trùng lặp.", before - len(df))

    logger.info("  ✓ orders: %d dòng sau làm sạch.", len(df))
    return df


def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch bảng customers.

    Xử lý:
    - Chuẩn hoá ID sang string
    - Chuẩn hoá tên thành phố (lowercase, strip)
    - Loại bỏ bản ghi trùng lặp theo customer_id

    Args:
        df: DataFrame thô của bảng customers.

    Returns:
        DataFrame đã làm sạch.
    """
    logger.info("Đang làm sạch bảng customers (%d dòng)...", len(df))
    df = df.copy()

    # Chuẩn hoá ID
    df["customer_id"] = df["customer_id"].astype(str).str.strip()
    df["customer_unique_id"] = df["customer_unique_id"].astype(str).str.strip()

    # Chuẩn hoá tên thành phố
    df["customer_city"] = (
        df["customer_city"].astype(str).str.strip().str.lower().str.title()
    )
    df["customer_state"] = df["customer_state"].astype(str).str.strip().str.upper()

    # Chuẩn hoá zip_code_prefix sang int (nếu chưa)
    df["customer_zip_code_prefix"] = pd.to_numeric(
        df["customer_zip_code_prefix"], errors="coerce"
    ).astype("Int64")

    # Loại bỏ trùng lặp
    before = len(df)
    df = df.drop_duplicates(subset=["customer_id"], keep="first")
    if len(df) < before:
        logger.info("  Đã loại %d bản ghi trùng lặp.", before - len(df))

    logger.info("  ✓ customers: %d dòng sau làm sạch.", len(df))
    return df


def clean_products(
    df: pd.DataFrame,
    translation_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Làm sạch bảng products.

    Xử lý:
    - Điền giá trị thiếu cho kích thước sản phẩm bằng median
    - Dịch tên danh mục sản phẩm sang tiếng Anh
    - Chuẩn hoá ID sang string

    Args:
        df: DataFrame thô của bảng products.
        translation_df: Bảng dịch tên danh mục (Portuguese → English).

    Returns:
        DataFrame đã làm sạch.
    """
    logger.info("Đang làm sạch bảng products (%d dòng)...", len(df))
    df = df.copy()

    # Chuẩn hoá ID
    df["product_id"] = df["product_id"].astype(str).str.strip()

    # Điền missing cho các cột kích thước / trọng lượng bằng median
    dimension_cols = [
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "product_name_lenght",       # Lưu ý: tên cột gốc bị typo
        "product_description_lenght",
        "product_photos_qty",
    ]
    for col in dimension_cols:
        if col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                logger.info(
                    "  Điền %d giá trị thiếu cho '%s' bằng median=%.1f",
                    missing_count,
                    col,
                    median_val,
                )

    # Dịch tên danh mục sản phẩm
    if translation_df is not None:
        translation_map = dict(
            zip(
                translation_df["product_category_name"],
                translation_df["product_category_name_english"],
            )
        )
        df["product_category_name_english"] = (
            df["product_category_name"].map(translation_map)
        )
        # Các danh mục không có bản dịch → giữ nguyên tên gốc
        unmapped = df["product_category_name_english"].isna().sum()
        if unmapped > 0:
            logger.warning(
                "  ⚠ %d sản phẩm không có bản dịch danh mục → giữ tên gốc.",
                unmapped,
            )
            df["product_category_name_english"] = df[
                "product_category_name_english"
            ].fillna(df["product_category_name"])
    else:
        logger.warning("  ⚠ Không có bảng dịch → bỏ qua dịch danh mục.")
        df["product_category_name_english"] = df.get(
            "product_category_name", pd.Series(dtype=str)
        )

    # Điền missing cho category = 'unknown'
    df["product_category_name_english"] = (
        df["product_category_name_english"].fillna("unknown")
    )

    # Rename các cột bị typo trong dataset gốc
    rename_map = {
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Loại bỏ trùng lặp
    before = len(df)
    df = df.drop_duplicates(subset=["product_id"], keep="first")
    if len(df) < before:
        logger.info("  Đã loại %d bản ghi trùng lặp.", before - len(df))

    logger.info("  ✓ products: %d dòng sau làm sạch.", len(df))
    return df


def clean_order_items(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch bảng order_items.

    Xử lý:
    - Chuẩn hoá ID sang string
    - Validate giá trị price và freight_value (phải >= 0)
    - Parse shipping_limit_date sang datetime

    Args:
        df: DataFrame thô của bảng order_items.

    Returns:
        DataFrame đã làm sạch.
    """
    logger.info("Đang làm sạch bảng order_items (%d dòng)...", len(df))
    df = df.copy()

    # Chuẩn hoá ID
    for col in ["order_id", "product_id", "seller_id"]:
        df[col] = df[col].astype(str).str.strip()

    # Chuẩn hoá kiểu số
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce")

    # Validate: price và freight_value phải >= 0
    invalid_price = (df["price"] < 0).sum()
    invalid_freight = (df["freight_value"] < 0).sum()
    if invalid_price > 0:
        logger.warning("  ⚠ %d dòng có price < 0 → đặt về 0.", invalid_price)
        df.loc[df["price"] < 0, "price"] = 0
    if invalid_freight > 0:
        logger.warning(
            "  ⚠ %d dòng có freight_value < 0 → đặt về 0.", invalid_freight
        )
        df.loc[df["freight_value"] < 0, "freight_value"] = 0

    # Parse ngày
    if "shipping_limit_date" in df.columns:
        df["shipping_limit_date"] = pd.to_datetime(
            df["shipping_limit_date"], errors="coerce"
        )

    logger.info("  ✓ order_items: %d dòng sau làm sạch.", len(df))
    return df


def clean_payments(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch bảng payments.

    Xử lý:
    - Chuẩn hoá order_id
    - Validate payment_value >= 0
    - Chuẩn hoá payment_type

    Args:
        df: DataFrame thô của bảng payments.

    Returns:
        DataFrame đã làm sạch.
    """
    logger.info("Đang làm sạch bảng payments (%d dòng)...", len(df))
    df = df.copy()

    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["payment_type"] = df["payment_type"].astype(str).str.strip().str.lower()
    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce").fillna(0)

    # Validate
    invalid = (df["payment_value"] < 0).sum()
    if invalid > 0:
        logger.warning("  ⚠ %d dòng có payment_value < 0 → đặt về 0.", invalid)
        df.loc[df["payment_value"] < 0, "payment_value"] = 0

    logger.info("  ✓ payments: %d dòng sau làm sạch.", len(df))
    return df


def clean_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch bảng reviews.

    Xử lý:
    - Chuẩn hoá ID
    - Parse ngày tạo / trả lời review
    - Xử lý missing review comment

    Args:
        df: DataFrame thô của bảng reviews.

    Returns:
        DataFrame đã làm sạch.
    """
    logger.info("Đang làm sạch bảng reviews (%d dòng)...", len(df))
    df = df.copy()

    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["review_id"] = df["review_id"].astype(str).str.strip()

    # Parse ngày
    for col in ["review_creation_date", "review_answer_timestamp"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Điền missing comment
    df["review_comment_title"] = df["review_comment_title"].fillna("")
    df["review_comment_message"] = df["review_comment_message"].fillna("")

    # Validate review_score trong khoảng [1, 5]
    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce")
    df["review_score"] = df["review_score"].clip(1, 5)

    # Loại bỏ trùng lặp: giữ review mới nhất cho mỗi order
    before = len(df)
    df = df.sort_values("review_creation_date", ascending=False)
    df = df.drop_duplicates(subset=["order_id"], keep="first")
    if len(df) < before:
        logger.info(
            "  Đã loại %d review trùng (giữ mới nhất/order).", before - len(df)
        )

    logger.info("  ✓ reviews: %d dòng sau làm sạch.", len(df))
    return df


def clean_sellers(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch bảng sellers.

    Args:
        df: DataFrame thô của bảng sellers.

    Returns:
        DataFrame đã làm sạch.
    """
    logger.info("Đang làm sạch bảng sellers (%d dòng)...", len(df))
    df = df.copy()

    df["seller_id"] = df["seller_id"].astype(str).str.strip()
    df["seller_city"] = (
        df["seller_city"].astype(str).str.strip().str.lower().str.title()
    )
    df["seller_state"] = df["seller_state"].astype(str).str.strip().str.upper()
    df["seller_zip_code_prefix"] = pd.to_numeric(
        df["seller_zip_code_prefix"], errors="coerce"
    ).astype("Int64")

    # Loại bỏ trùng lặp
    before = len(df)
    df = df.drop_duplicates(subset=["seller_id"], keep="first")
    if len(df) < before:
        logger.info("  Đã loại %d bản ghi trùng lặp.", before - len(df))

    logger.info("  ✓ sellers: %d dòng sau làm sạch.", len(df))
    return df


def clean_geolocation(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch bảng geolocation.

    Xử lý:
    - Loại bỏ trùng lặp theo zip_code_prefix (giữ bản ghi đầu tiên)
    - Chuẩn hoá tên thành phố, bang

    Args:
        df: DataFrame thô của bảng geolocation.

    Returns:
        DataFrame đã làm sạch (1 dòng / zip_code_prefix).
    """
    logger.info("Đang làm sạch bảng geolocation (%d dòng)...", len(df))
    df = df.copy()

    # Chuẩn hoá
    df["geolocation_city"] = (
        df["geolocation_city"].astype(str).str.strip().str.lower().str.title()
    )
    df["geolocation_state"] = (
        df["geolocation_state"].astype(str).str.strip().str.upper()
    )

    # Loại bỏ trùng lặp: giữ 1 bản ghi đầu tiên cho mỗi zip_code_prefix
    before = len(df)
    df = df.drop_duplicates(
        subset=["geolocation_zip_code_prefix"], keep="first"
    )
    logger.info(
        "  Đã giảm từ %d → %d dòng (deduplicate theo zip_code_prefix).",
        before,
        len(df),
    )

    logger.info("  ✓ geolocation: %d dòng sau làm sạch.", len(df))
    return df


# ---------------------------------------------------------------------------
# Hàm orchestrator: làm sạch toàn bộ
# ---------------------------------------------------------------------------

def clean_all(
    raw_dir: str = "data/raw",
    output_dir: str = "data/processed",
) -> dict[str, pd.DataFrame]:
    """Orchestrator: load dữ liệu thô, làm sạch tất cả, lưu Parquet.

    Args:
        raw_dir: Thư mục chứa CSV thô.
        output_dir: Thư mục xuất Parquet đã làm sạch.

    Returns:
        Dictionary {tên_bảng: DataFrame đã làm sạch}.
    """
    logger.info("=" * 60)
    logger.info("BẮT ĐẦU PIPELINE LÀM SẠCH DỮ LIỆU")
    logger.info("=" * 60)

    # Bước 1: Load dữ liệu thô
    raw = load_raw_data(raw_dir)

    # Bước 2: Làm sạch từng bảng
    cleaned: dict[str, pd.DataFrame] = {}

    if "orders" in raw:
        cleaned["orders"] = clean_orders(raw["orders"])

    if "customers" in raw:
        cleaned["customers"] = clean_customers(raw["customers"])

    if "products" in raw:
        translation_df = raw.get("category_translation")
        cleaned["products"] = clean_products(raw["products"], translation_df)

    if "order_items" in raw:
        cleaned["order_items"] = clean_order_items(raw["order_items"])

    if "payments" in raw:
        cleaned["payments"] = clean_payments(raw["payments"])

    if "reviews" in raw:
        cleaned["reviews"] = clean_reviews(raw["reviews"])

    if "sellers" in raw:
        cleaned["sellers"] = clean_sellers(raw["sellers"])

    if "geolocation" in raw:
        cleaned["geolocation"] = clean_geolocation(raw["geolocation"])

    # Bước 3: Lưu kết quả Parquet
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for name, df in cleaned.items():
        parquet_file = output_path / f"{name}.parquet"
        df.to_parquet(parquet_file, index=False, engine="pyarrow")
        logger.info("  💾 Saved: %s (%d rows)", parquet_file.name, len(df))

    logger.info("=" * 60)
    logger.info("✅ HOÀN TẤT LÀM SẠCH → %s", output_path.resolve())
    logger.info("=" * 60)

    return cleaned


if __name__ == "__main__":
    clean_all()
