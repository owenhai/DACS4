# DACS4 - Automated Data Insights Engine

Hệ thống phân tích dữ liệu thương mại điện tử Olist bằng **DuckDB**, kết hợp
**Text-to-SQL** và mô hình **Gemini Flash**. Người dùng có thể đặt câu hỏi
bằng ngôn ngữ tự nhiên; pipeline sẽ tạo SQL, thực thi trên Star Schema và
trả về kết quả phân tích.

## Tiến độ dự án

- **Tuần 1 - Hoàn thành:** Thu thập, làm sạch dữ liệu Olist, xây dựng Star
  Schema và nạp dữ liệu vào DuckDB.
- **Tuần 2 - Hoàn thành cơ bản:** Tích hợp Gemini Flash, Prompt Engineering,
  Few-shot Prompting và pipeline Text-to-SQL.
- **Tuần 3 - Tiếp theo:** SQL Guardrails và nâng cấp Self-Correction Loop.
- **Tuần 4-8:** Visualization, giao diện Streamlit, đánh giá, báo cáo và
  đóng gói.

## Yêu cầu

- Python 3.10 trở lên
- API key của Google Gemini nếu muốn gọi pipeline Text-to-SQL
- Model mặc định: `gemini-3.8-flash`

## Cài đặt

Mở Terminal tại thư mục gốc của dự án:

```powershell
cd "D:\Project _Lab_Doc\DA\DACS4"
python -m pip install -r requirements.txt
```

Tạo file `.env` ở thư mục gốc và thêm API key:

```text
GOOGLE_API_KEY=your_google_gemini_api_key
```

Không commit file `.env` hoặc API key lên Git.

## Chạy pipeline dữ liệu

Chạy lần lượt từ thư mục gốc:

```powershell
python -m src.data.download_dataset
python -m src.data.clean_data
python -m src.data.star_schema
```

Pipeline tạo ra:

- Dữ liệu CSV gốc trong `data/raw/`
- Dữ liệu Parquet đã xử lý trong `data/processed/`
- Database DuckDB tại `data/database/olist_analytics.duckdb`

Lệnh tải dữ liệu yêu cầu cấu hình quyền truy cập Kaggle. Nếu dữ liệu đã có
sẵn trong `data/raw/`, có thể bỏ qua bước download.

## Kiểm tra dự án

Chạy toàn bộ unit test:

```powershell
python -m unittest discover -s tests -v
```

Kết quả hiện tại: **21 tests passed**.

Kiểm tra metadata và báo cáo EDA:

```powershell
python -m src.data.schema_metadata
python -m src.data.eda
```

Các test hiện có kiểm tra:

- Database có đủ các bảng Star Schema.
- Số lượng bản ghi của bảng fact và dữ liệu nguồn.
- Khóa liên kết giữa fact và dimension không bị mồ côi.
- Schema metadata khớp với database.
- Prompt, few-shot examples và SQL extraction của Text-to-SQL.

## Cấu trúc dữ liệu

Database gồm bảng fact:

- `fact_orders`

Và các bảng dimension:

- `dim_customers`
- `dim_products`
- `dim_sellers`
- `dim_date`
- `dim_geolocation`

## Cấu trúc mã nguồn

```text
config/                 Cấu hình đường dẫn và Gemini
data/raw/               Dữ liệu CSV gốc
data/processed/         Dữ liệu Parquet đã làm sạch
data/database/          Database DuckDB
src/data/               Download, cleaning, EDA, schema và ETL
src/models/             Gemini client, prompt và Text-to-SQL
tests/                  Unit tests cho Week 1 và Week 2
docs/                   Tài liệu Star Schema và báo cáo tuần
```

## Ghi chú về giao diện web

Để giảm thời gian phản hồi của pipeline Text-to-SQL, cấu hình mặc định hiện
dùng 2 ví dụ few-shot, tắt bước phân rã câu hỏi và chỉ thử self-correction
thêm 1 lần. Có thể truyền `num_few_shot` hoặc `max_corrections` khi khởi tạo
`TextToSQLPipeline` nếu cần ưu tiên độ chính xác cho câu hỏi phức tạp.
Khi Gemini trả lỗi tạm thời như 503 hoặc 429, client tự retry với exponential
backoff và jitter. Có thể đặt `GEMINI_FALLBACK_MODEL` trong biến môi trường để
thử model dự phòng sau khi model chính liên tục quá tải.

Thư viện Streamlit đã được khai báo trong `requirements.txt`, nhưng giao diện
web chưa được triển khai. Sau khi hoàn thành phần UI, ứng dụng sẽ được chạy
bằng:

```powershell
streamlit run app.py
```

## Tài liệu liên quan

- [Star Schema](docs/STAR_SCHEMA.md)
- [Tổng kết Week 1](docs/WEEK1_SUMMARY.md)
- [Theo dõi tiến độ](PROGRESS_TRACKER.md)
- [Đề cương dự án](project_proposal.md)
