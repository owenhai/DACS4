"""
Cấu hình chung cho dự án DACS4 - Automated Data Insights Engine.

Module này chứa các hằng số cấu hình cho đường dẫn dữ liệu,
cơ sở dữ liệu, và metadata của schema Star Schema.
"""

from pathlib import Path

# === Đường dẫn gốc của dự án ===
# Lấy thư mục gốc dự án từ vị trí file config hiện tại
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# === Đường dẫn dữ liệu ===
# Thư mục chứa dữ liệu thô từ Kaggle (Olist dataset)
RAW_DATA_DIR: Path = PROJECT_ROOT / "data" / "raw"

# Thư mục chứa dữ liệu đã xử lý (sau ETL)
PROCESSED_DATA_DIR: Path = PROJECT_ROOT / "data" / "processed"

# === Đường dẫn cơ sở dữ liệu ===
# File DuckDB chứa Star Schema cho phân tích
DATABASE_DIR: Path = PROJECT_ROOT / "data" / "database"
DATABASE_PATH: Path = DATABASE_DIR / "olist_analytics.duckdb"

# === Metadata của Star Schema ===
# Mô tả cấu trúc bảng để LLM hiểu ngữ cảnh khi sinh SQL
SCHEMA_METADATA: dict[str, dict] = {
    # Bảng sự kiện (Fact table) - chứa dữ liệu giao dịch
    "fact_orders": {
        "description": "Bảng sự kiện chứa thông tin đơn hàng và chi tiết sản phẩm",
        "columns": {},  # Sẽ được cập nhật sau khi thiết kế schema
    },
    # Bảng chiều khách hàng (Dimension)
    "dim_customers": {
        "description": "Bảng chiều chứa thông tin khách hàng",
        "columns": {},
    },
    # Bảng chiều sản phẩm (Dimension)
    "dim_products": {
        "description": "Bảng chiều chứa thông tin sản phẩm",
        "columns": {},
    },
    # Bảng chiều người bán (Dimension)
    "dim_sellers": {
        "description": "Bảng chiều chứa thông tin người bán",
        "columns": {},
    },
    # Bảng chiều thời gian (Dimension)
    "dim_date": {
        "description": "Bảng chiều thời gian để phân tích theo ngày/tháng/quý/năm",
        "columns": {},
    },
    # Bảng chiều vị trí địa lý (Dimension)
    "dim_geolocation": {
        "description": "Bảng chiều chứa thông tin vị trí địa lý",
        "columns": {},
    },
}

# === Cấu hình LLM ===
# Model Gemini Flash dùng cho Text-to-SQL
GEMINI_MODEL: str = "gemini-2.0-flash"

# Nhiệt độ sinh (temperature) - giá trị thấp cho kết quả ổn định
GEMINI_TEMPERATURE: float = 0.1

# Số token tối đa cho phản hồi
GEMINI_MAX_OUTPUT_TOKENS: int = 2048
