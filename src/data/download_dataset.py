"""Module tải bộ dữ liệu Olist Brazilian E-Commerce từ Kaggle.

Sử dụng kagglehub để download dataset và copy các file CSV
vào thư mục data/raw của project.
"""

import logging
import shutil
from pathlib import Path

import kagglehub

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Tên dataset trên Kaggle
KAGGLE_DATASET: str = "olistbr/brazilian-ecommerce"

# Danh sách các file CSV cần có trong dataset
EXPECTED_FILES: list[str] = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


def download_olist_dataset(target_dir: str = "data/raw") -> Path:
    """Tải bộ dữ liệu Olist về thư mục chỉ định.

    Sử dụng kagglehub để download dataset 'olistbr/brazilian-ecommerce'.
    Copy các file CSV vào target_dir.

    Args:
        target_dir: Đường dẫn thư mục đích để lưu dữ liệu thô.

    Returns:
        Path tới thư mục chứa dữ liệu đã tải.

    Raises:
        RuntimeError: Khi download thất bại hoặc thiếu file.
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    logger.info("Thư mục đích: %s", target.resolve())

    # --- Download dataset qua kagglehub ---
    try:
        logger.info("Đang tải dataset '%s' từ Kaggle...", KAGGLE_DATASET)
        dataset_path = kagglehub.dataset_download(KAGGLE_DATASET)
        dataset_path = Path(dataset_path)
        logger.info("Dataset đã tải về: %s", dataset_path)
    except Exception as exc:
        logger.error("Lỗi khi tải dataset: %s", exc)
        raise RuntimeError(f"Không thể tải dataset từ Kaggle: {exc}") from exc

    # --- Copy các file CSV sang thư mục đích ---
    csv_files = list(dataset_path.glob("*.csv"))
    if not csv_files:
        raise RuntimeError(
            f"Không tìm thấy file CSV nào trong {dataset_path}"
        )

    copied_count = 0
    skipped_count = 0

    for csv_file in csv_files:
        dest = target / csv_file.name
        if not dest.exists():
            shutil.copy2(csv_file, dest)
            logger.info("  ✓ Đã copy: %s", csv_file.name)
            copied_count += 1
        else:
            logger.info("  ⏭ Đã tồn tại: %s", csv_file.name)
            skipped_count += 1

    # --- Kiểm tra tính đầy đủ ---
    missing = [
        f for f in EXPECTED_FILES if not (target / f).exists()
    ]
    if missing:
        logger.warning(
            "Thiếu %d file: %s", len(missing), ", ".join(missing)
        )

    logger.info(
        "✅ Hoàn tất! Copied: %d | Skipped: %d | Tổng CSV: %d",
        copied_count,
        skipped_count,
        len(csv_files),
    )
    return target


if __name__ == "__main__":
    download_olist_dataset()
