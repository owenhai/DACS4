# Tóm tắt Tuần 1

## 1. Tuần 1 làm về gì?

Tuần 1 xây dựng phần nền dữ liệu cho dự án **Automated Data Insights Engine**.

Bộ dữ liệu sử dụng là **Olist Brazilian E-Commerce Dataset**, mô tả hoạt động thương mại điện tử tại Brazil:

- Đơn hàng và trạng thái giao hàng
- Khách hàng
- Sản phẩm và danh mục sản phẩm
- Người bán
- Thanh toán
- Đánh giá khách hàng
- Chi phí vận chuyển
- Thời gian giao hàng
- Vị trí địa lý

Mục tiêu của tuần này là biến các file CSV thô thành một cơ sở dữ liệu phân tích có cấu trúc, sẵn sàng cho Tuần 2 xây dựng Text-to-SQL với Gemini.

## 2. Đã làm những gì?

### Thu thập dữ liệu

Đã lưu đủ 9 file CSV gốc vào `data/raw/`:

- orders
- order_items
- customers
- products
- sellers
- payments
- reviews
- geolocation
- category translation

### Làm sạch dữ liệu

Module `src/data/clean_data.py` thực hiện các công việc chính:

- Đọc toàn bộ CSV
- Chuẩn hóa ID và chuỗi ký tự
- Chuyển cột ngày sang kiểu datetime
- Chuẩn hóa kiểu số
- Xử lý giá trị thiếu
- Dịch tên danh mục sản phẩm sang tiếng Anh
- Giới hạn điểm đánh giá trong khoảng 1 đến 5
- Xử lý giá và phí vận chuyển âm
- Loại bỏ bản ghi trùng lặp
- Lưu dữ liệu đã xử lý dưới dạng Parquet trong `data/processed/`

### Khám phá dữ liệu ban đầu

Module `src/data/eda.py` tổng hợp cho từng file:

- Số dòng
- Số cột
- Số ô bị thiếu
- Số dòng trùng lặp
- Kiểu dữ liệu của các cột

### Thiết kế Star Schema

Cơ sở dữ liệu gồm một bảng fact và các bảng dimension:

- `fact_orders`: dữ liệu giao dịch ở mức một sản phẩm trong một đơn hàng
- `dim_customers`: thông tin khách hàng
- `dim_products`: thông tin sản phẩm
- `dim_sellers`: thông tin người bán
- `dim_date`: thông tin ngày, tháng, quý, năm
- `dim_geolocation`: thông tin địa lý

Các measure chính trong `fact_orders`:

- `price`
- `freight_value`
- `payment_value`
- `review_score`
- `delivery_days`

### Nạp dữ liệu vào DuckDB

Module `src/data/star_schema.py` thực hiện:

1. Đọc các file Parquet đã làm sạch
2. Tạo các bảng dimension
3. Join dữ liệu đơn hàng, sản phẩm, thanh toán và review
4. Tạo bảng `fact_orders`
5. Tạo khóa chính và khóa ngoại
6. Nạp toàn bộ vào `data/database/olist_analytics.duckdb`

### Tạo Schema Metadata

Module `src/data/schema_metadata.py` mô tả:

- Tên và mục đích của từng bảng
- Tên cột và kiểu dữ liệu
- Khóa chính, khóa ngoại
- Quan hệ giữa các bảng
- Một số giá trị mẫu
- Mô tả schema để LLM sử dụng ở Tuần 2

## 3. Kết quả chính

| Bảng | Số dòng |
|---|---:|
| `fact_orders` | 112,650 |
| `dim_customers` | 99,441 |
| `dim_products` | 32,951 |
| `dim_sellers` | 3,095 |
| `dim_date` | 1,461 |
| `dim_geolocation` | 19,015 |

Các kiểm tra hiện tại đạt **5/5 tests**:

- Database có đủ các bảng cần thiết
- `fact_orders` có đúng số dòng
- Các khóa dimension không bị orphan
- Metadata khớp với database
- Row count của 9 file raw khớp với dữ liệu đã kiểm tra
- Các query phân tích mẫu chạy được

## 4. Cách chạy lại pipeline

Chạy từ thư mục gốc của project:

```powershell
python -m src.data.clean_data
python -m src.data.star_schema
python -m src.data.eda
python -m unittest discover -s tests -v
```

## 5. Kết luận

Tuần 1 đã hoàn thành phần nền dữ liệu của dự án:

```text
CSV thô -> Làm sạch -> Parquet -> Star Schema -> DuckDB -> Schema Metadata
```

Sau Tuần 1, database đã sẵn sàng để Tuần 2 xây dựng pipeline:

```text
Câu hỏi tiếng Việt -> Gemini Flash -> SQL -> DuckDB
```

## 6. Công cụ và thư viện đã sử dụng

| Công cụ / thư viện | Vai trò trong Tuần 1 |
|---|---|
| Python | Ngôn ngữ chính để xây dựng pipeline ETL và validation |
| pandas | Đọc CSV, làm sạch, biến đổi và join dữ liệu |
| DuckDB | Lưu trữ và truy vấn database phân tích |
| PyArrow / Parquet | Lưu dữ liệu trung gian đã làm sạch |
| pathlib | Quản lý đường dẫn file và thư mục |
| logging | Ghi log quá trình load, clean và build schema |
| unittest | Viết và chạy các bài kiểm tra Tuần 1 |
| Kaggle | Nguồn tải bộ Olist Brazilian E-Commerce Dataset |
| Mermaid | Vẽ sơ đồ quan hệ Star Schema trong tài liệu |

## 7. Các file quan trọng

| File | Chức năng |
|---|---|
| `src/data/download_dataset.py` | Tải bộ dữ liệu Olist |
| `src/data/clean_data.py` | Làm sạch và lưu Parquet |
| `src/data/eda.py` | Thống kê ban đầu cho 9 file CSV |
| `src/data/star_schema.py` | Tạo Star Schema và nạp DuckDB |
| `src/data/schema_metadata.py` | Mô tả schema cho LLM |
| `tests/test_week1_validation.py` | Kiểm tra kết quả Tuần 1 |
| `data/database/olist_analytics.duckdb` | Database phân tích cuối cùng |
