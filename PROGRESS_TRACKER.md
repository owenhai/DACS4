# 📊 DACS4 - TIẾN ĐỘ DỰ ÁN

> **Dự án:** Automated Data Insights Engine (Text-to-SQL + LLM)  
> **Thời gian:** 8 tuần  
> **Cập nhật lần cuối:** 24/11/2026

---

## 📈 TỔNG QUAN TIẾN ĐỘ

| Tuần | Nội dung chính | Trạng thái | Hoàn thành |
|:----:|----------------|:----------:|:----------:|
| 1 | Thu thập & Xử lý dữ liệu, Star Schema, DuckDB | 🟢 Hoàn thành | ▓▓▓▓▓▓▓▓▓▓ 100% |
| 2 | Tích hợp Gemini Flash, Prompt Engineering, Text-to-SQL | 🟢 Hoàn thành | ▓▓▓▓▓▓▓▓▓▓ 100% |
| 3 | SQL Guardrails & Self-Correction Loop | 🟢 Hoàn thành | ▓▓▓▓▓▓▓▓▓▓ 100% |
| 4 | Auto Visualization & Insight Generation | 🟢 Hoàn thành | ▓▓▓▓▓▓▓▓▓▓ 100% |
| 5 | Giao diện Streamlit & Tích hợp hệ thống | 🟢 Hoàn thành | ▓▓▓▓▓▓▓▓▓▓ 100% |
| 6 | Kiểm thử & Đánh giá hiệu năng | 🟢 Hoàn thành | ▓▓▓▓▓▓▓▓▓▓ 100% |
| 7 | Viết báo cáo đồ án | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 8 | Đóng gói, Slide & Video demo | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |

**Tiến độ tổng thể:** ▓▓▓▓▓▓▓▓░░ **75%** _(6/8 tuần đã hoàn thành)_

---

## 🟢 TUẦN 1 — Thu thập dữ liệu, Star Schema & DuckDB `Hoàn thành`

### 1.1 Thu thập bộ dữ liệu Olist E-Commerce ⏱️ _~3 giờ_

- [x] Tải bộ dữ liệu Olist Brazilian E-Commerce từ Kaggle
- [x] Kiểm tra đầy đủ các file CSV (9 file):
  - [x] `olist_orders_dataset.csv`
  - [x] `olist_order_items_dataset.csv`
  - [x] `olist_order_payments_dataset.csv`
  - [x] `olist_order_reviews_dataset.csv`
  - [x] `olist_products_dataset.csv`
  - [x] `olist_customers_dataset.csv`
  - [x] `olist_sellers_dataset.csv`
  - [x] `olist_geolocation_dataset.csv`
  - [x] `product_category_name_translation.csv`
- [x] Tạo thư mục `data/raw/` và lưu trữ dữ liệu gốc
- [x] Viết script khám phá dữ liệu ban đầu (EDA sơ bộ): shape, dtypes, null counts

### 1.2 Làm sạch & Chuẩn hóa dữ liệu ⏱️ _~5 giờ_

- [x] Phân tích giá trị khuyết thiếu (missing values) cho từng bảng
  - [x] Xác định chiến lược xử lý cho từng cột (drop / fill / impute)
  - [x] Ghi nhận tỉ lệ missing và lý do xử lý qua EDA và log pipeline
- [x] Xử lý giá trị khuyết thiếu
  - [x] Xử lý null trong `order_delivered_customer_date`
    - [x] Xử lý null trong `order_approved_at` (giữ `NaT` để phản ánh đơn chưa duyệt)
    - [x] Xử lý null trong `product_category_name`
    - [x] Xử lý null trong `review_comment_title`, `review_comment_message`
- [x] Chuẩn hóa kiểu dữ liệu
  - [x] Chuyển các cột ngày tháng sang `datetime`
  - [x] Chuẩn hóa kiểu số (int, float) cho price, freight, dimensions
  - [x] Chuẩn hóa kiểu chuỗi (string) – loại bỏ khoảng trắng thừa
- [x] Dịch tên danh mục sản phẩm từ tiếng Bồ Đào Nha sang tiếng Anh
- [x] Loại bỏ bản ghi trùng lặp (nếu có)
- [x] Tạo thư mục `data/processed/` và lưu dữ liệu đã làm sạch

### 1.3 Thiết kế lược đồ Star Schema ⏱️ _~4 giờ_

- [x] Vẽ sơ đồ ERD cho Star Schema
- [x] Thiết kế bảng **Fact: `fact_orders`**
  - [x] Xác định các khóa ngoại (FK) liên kết đến Dimension
  - [x] Xác định các measure: `price`, `freight_value`, `payment_value`, `review_score`
  - [x] Định nghĩa granularity (mức chi tiết: order_item level)
- [x] Thiết kế bảng **Dimension: `dim_customers`**
  - [x] Các cột: `customer_id`, `customer_unique_id`, `city`, `state`, `zip_code_prefix`
- [x] Thiết kế bảng **Dimension: `dim_products`**
  - [x] Các cột: `product_id`, `category_name`, `category_name_english`, `weight_g`, `length_cm`, `height_cm`, `width_cm`, `photos_qty`, `description_length`, `name_length`
- [x] Thiết kế bảng **Dimension: `dim_sellers`**
  - [x] Các cột: `seller_id`, `seller_city`, `seller_state`, `seller_zip_code_prefix`
- [x] Thiết kế bảng **Dimension: `dim_date`** (bảng thời gian)
  - [x] Các cột: `date_key`, `full_date`, `year`, `quarter`, `month`, `month_name`, `week`, `day_of_week`, `day_name`, `is_weekend`
- [x] Thiết kế bảng **Dimension: `dim_geolocation`**
  - [x] Các cột: `zip_code_prefix`, `lat`, `lng`, `city`, `state`

### 1.4 Nạp dữ liệu vào DuckDB ⏱️ _~4 giờ_

- [x] Cài đặt thư viện `duckdb` trong môi trường ảo
- [x] Viết script ETL nạp dữ liệu từ CSV/processed → DuckDB
  - [x] Tạo database file `data/database/olist_analytics.duckdb`
  - [x] Tạo bảng `dim_customers` và nạp dữ liệu
  - [x] Tạo bảng `dim_products` và nạp dữ liệu
  - [x] Tạo bảng `dim_sellers` và nạp dữ liệu
  - [x] Tạo bảng `dim_date` và nạp dữ liệu (generate từ date range)
  - [x] Tạo bảng `dim_geolocation` và nạp dữ liệu
  - [x] Tạo bảng `fact_orders` và nạp dữ liệu (JOIN từ nhiều bảng nguồn)
- [x] Thiết lập khóa chính (PRIMARY KEY) và ràng buộc (CONSTRAINTS)
- [x] Kiểm tra tính toàn vẹn dữ liệu sau khi nạp
  - [x] So sánh row count giữa nguồn và DuckDB
  - [x] Chạy vài truy vấn kiểm tra mẫu

### 1.5 Xây dựng Schema Metadata (Từ điển cấu trúc) ⏱️ _~3 giờ_

- [x] Tạo file `schema_metadata.py` hoặc `schema_metadata.json`
- [x] Mô tả chi tiết từng bảng:
  - [x] Tên bảng, mô tả nghiệp vụ (bằng tiếng Anh)
  - [x] Danh sách cột: tên, kiểu dữ liệu, mô tả, ví dụ giá trị
  - [x] Quan hệ giữa các bảng (khóa chính, khóa ngoại)
- [x] Bổ sung các ví dụ truy vấn SQL mẫu (5-10 câu) cho few-shot prompting
- [x] Viết hàm `get_schema_description()` trả về chuỗi mô tả schema cho LLM
- [x] Unit test: kiểm tra schema metadata khớp với bảng thực trong DuckDB

### 1.6 Tài liệu & Kiểm tra cuối tuần ⏱️ _~1 giờ_

- [x] Cập nhật `README.md` với hướng dẫn cài đặt ban đầu
- [ ] Commit code lên Git với message rõ ràng
- [x] Review lại toàn bộ output tuần 1

> **Tổng thời gian ước tính Tuần 1:** ~20 giờ

---

## 🟢 TUẦN 2 — Tích hợp Gemini Flash & Pipeline Text-to-SQL `Hoàn thành`

### 2.1 Cấu hình môi trường & Google GenAI SDK ⏱️ _~2 giờ_

- [x] Tạo tài khoản Google AI Studio và lấy API Key
- [x] Cài đặt thư viện `google-genai` (Google GenAI SDK)
- [x] Thiết lập file `.env` lưu `GOOGLE_API_KEY`
- [x] Viết module `llm_client.py` kết nối Gemini Flash
- [x] Test kết nối cơ bản với Gemini Flash (`gemini-3.8-flash`)
- [x] Xác nhận rate limits và pricing tier

### 2.2 Thiết kế Prompt Template ⏱️ _~5 giờ_

- [x] Nghiên cứu các kỹ thuật prompt engineering cho Text-to-SQL
  - [x] Schema Linking: gắn schema vào prompt
  - [x] Few-shot Prompting: cung cấp ví dụ câu hỏi → SQL
  - [x] Task Decomposition: yêu cầu LLM phân tích câu hỏi trước khi viết SQL
- [x] Xây dựng System Prompt chính
  - [x] Mô tả vai trò của LLM (SQL expert cho DuckDB)
  - [x] Nhúng schema metadata vào prompt
  - [x] 13 quy tắc viết SQL (chỉ SELECT, dùng alias, xử lý NULL, ROUND, ...)
  - [x] Ràng buộc output format (chỉ trả SQL, không markdown)
- [x] Tạo bộ Few-shot Examples (10 cặp câu hỏi/SQL)
  - [x] 3 ví dụ Easy: đếm, tổng, trung bình
  - [x] 3 ví dụ Medium: GROUP BY + JOIN, ORDER BY, filter theo năm
  - [x] 4 ví dụ Hard: CTE, multi-JOIN, HAVING, tính phần trăm
- [x] Lưu template trong `src/models/prompt_templates.py`
- [x] Chuẩn bị correction prompt cho Self-Correction Loop

### 2.3 Xây dựng Pipeline Text-to-SQL cơ bản ⏱️ _~6 giờ_

- [x] Tạo module `text_to_sql.py`
- [x] Viết class `TextToSQLPipeline`:
  - [x] `__init__()`: khởi tạo GenAI client, load schema metadata
  - [x] `_generate_sql()`: gọi Gemini Flash, trả về SQL
  - [x] `_execute_sql()`: thực thi SQL trên DuckDB (read-only)
  - [x] `_extract_sql()`: trích xuất SQL từ markdown/text response
  - [x] `_execute_with_correction()`: Self-Correction Loop cơ bản
  - [x] `ask()`: pipeline end-to-end trả về QueryResult
- [x] Xử lý response parsing: hỗ trợ code block, plain SQL, CTE
- [x] Thêm logging chi tiết (câu hỏi → prompt → SQL → kết quả)
- [x] Xử lý retry logic cho API calls (max 3 retries)

### 2.4 Test & Debug Pipeline ⏱️ _~4 giờ_

- [x] Viết 16 unit tests (tất cả passed)
- [x] Test SQL extraction từ nhiều format response
- [x] Test prompt template structure và few-shot selection
- [x] Test schema metadata integration
- [x] Commit code & cập nhật tài liệu

> **Tổng thời gian ước tính Tuần 2:** ~17 giờ

---

## 🟢 TUẦN 3 — SQL Guardrails & Self-Correction Loop `Hoàn thành`

### 3.1 Xây dựng module SQL Guardrails ⏱️ _~5 giờ_ `Hoàn thành`

- [x] Cài đặt thư viện `sqlparse`
- [x] Tạo module `sql_guardrails.py`
- [x] Implement các bộ lọc bảo mật:
  - [x] **Whitelist kiểm tra**: chỉ cho phép `SELECT` statements
  - [x] **Blacklist từ khóa**: chặn `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`
  - [x] **Chặn comment injection**: loại bỏ `--`, `/* */`
  - [x] **Giới hạn độ phức tạp**: số lượng JOIN tối đa, subquery depth
  - [x] **Kiểm tra tên bảng/cột**: chỉ cho phép bảng/cột có trong schema
- [x] Viết hàm `validate_sql(sql: str) -> ValidationResult`
  - [x] Trả về `is_valid`, `error_message`, `sanitized_sql`
- [x] Viết hàm `sanitize_sql(sql: str) -> str`
  - [x] Loại bỏ LIMIT nếu cần, thêm LIMIT mặc định
  - [x] Format lại SQL cho dễ đọc
- [x] Unit tests cho tất cả các trường hợp bảo mật

### 3.2 Xây dựng Self-Correction Loop ⏱️ _~6 giờ_ `Hoàn thành`

- [x] Thiết kế luồng tự sửa lỗi:
  ```
  Câu hỏi → SQL → Validate → Execute → Nếu lỗi → Gửi lỗi cho LLM → SQL mới → Lặp lại (tối đa 3 lần)
  ```
- [x] Tạo module `self_correction.py`
- [x] Implement `SelfCorrectionLoop`:
  - [x] `attempt_execution(sql: str) -> ExecutionResult`: thực thi và bắt lỗi
  - [x] `build_correction_prompt(original_question, failed_sql, error_msg) -> str`: tạo prompt sửa lỗi
  - [x] `run_with_correction(question: str, max_retries: int = 3) -> dict`: vòng lặp chính
- [x] Xử lý các loại lỗi phổ biến:
  - [x] Lỗi cú pháp SQL (syntax error)
  - [x] Lỗi tên bảng/cột không tồn tại
  - [x] Lỗi kiểu dữ liệu không tương thích
  - [x] Lỗi timeout (query quá chậm)
  - [x] Kết quả rỗng (empty result)
- [x] Logging chi tiết: ghi lại từng lần thử và lỗi
- [x] Đo metrics: số lần retry trung bình, tỉ lệ sửa thành công

### 3.3 Tích hợp vào Pipeline chính ⏱️ _~3 giờ_ `Hoàn thành`

- [x] Tích hợp `sql_guardrails` vào `TextToSQLPipeline`
- [x] Tích hợp `self_correction` vào `TextToSQLPipeline`
- [x] Cập nhật hàm `run()` với luồng: validate → execute → correct (nếu cần)
- [x] Test end-to-end với 15 câu hỏi (gồm cả câu cố tình gây lỗi)
- [x] Cập nhật tài liệu

### 3.4 Kiểm thử bảo mật ⏱️ _~2 giờ_ `Hoàn thành`

- [x] Tạo bộ test SQL injection attempts
- [x] Test với các prompt cố tình yêu cầu xóa/sửa dữ liệu
- [x] Xác nhận tất cả đều bị chặn
- [x] Ghi nhận kết quả vào báo cáo kiểm thử

**Kết quả test (19/11/2026):** `python -m pytest tests` → **99 passed, 2 skipped**.
- `tests/test_week3_guardrails.py`: 93 tests (21 mẫu tấn công bị chặn, 10 few-shot SQL hợp lệ, 15 câu hỏi end-to-end).
- End-to-end dùng LLM giả lập + DuckDB thật; chưa chạy được với Gemini thật (API trả 503).
- 2 test bị skip là test gọi Gemini thật.
- Hạn chế: guardrails chỉ kiểm tra cột dạng `alias.column`; cột không có alias để DuckDB + Self-Correction xử lý.

> **Tổng thời gian ước tính Tuần 3:** ~16 giờ

---

## 🟢 TUẦN 4 — Auto Visualization & Insight Generation `Hoàn thành`

### 4.1 Xây dựng thuật toán phân loại biểu đồ ⏱️ _~5 giờ_ `Hoàn thành`

- [x] Tạo module `src/visualization/chart_classifier.py`
- [x] Phân tích đặc điểm dữ liệu đầu ra để chọn biểu đồ:
  - [x] **1 cột categorical + 1 cột numeric** → Bar Chart
  - [x] **1 cột datetime/temporal + 1 cột numeric** → Line Chart (hỗ trợ nhiều đường)
  - [x] **1 cột categorical + 1 cột numeric (tỉ lệ, ≤ 8 nhóm)** → Pie Chart
  - [x] **2 cột numeric** → Scatter Plot
  - [x] **1 cột numeric (phân phối)** → Histogram
  - [x] **Nhiều cột categorical + numeric** → Grouped Bar
  - [x] **Dữ liệu có lat/lng** → Map
  - [x] **1 dòng có số** → KPI; **không có số / rỗng** → Table
- [x] Viết hàm `classify_chart_type(df, sql, question) -> ChartSpec`
- [x] Viết hàm `detect_column_roles(df) -> dict`
  - [x] Phân biệt: categorical, numeric, datetime, temporal, latitude, longitude, identifier
- [x] Unit tests với nhiều dạng DataFrame khác nhau

### 4.2 Tích hợp Plotly Express ⏱️ _~5 giờ_ `Hoàn thành`

- [x] Cài đặt `plotly` (7.1.0)
- [x] Tạo module `src/visualization/chart_generator.py`
- [x] Implement từng loại biểu đồ:
  - [x] `create_bar_chart(df, x_col, y_col, title) -> Figure`
  - [x] `create_line_chart(df, x_col, y_col, title) -> Figure`
  - [x] `create_pie_chart(df, names_col, values_col, title) -> Figure`
  - [x] `create_scatter_plot(df, x_col, y_col, title) -> Figure`
  - [x] `create_histogram(df, col, title) -> Figure`
  - [x] `create_grouped_bar(df, x_col, y_col, color_col, title) -> Figure`
  - [x] Bổ sung `create_map`, `create_kpi`, `create_table`
- [x] Thiết kế theme/style thống nhất cho tất cả biểu đồ (`apply_theme`, `COLOR_PALETTE`)
- [x] Hàm tổng hợp `auto_generate_chart(df, sql, question) -> tuple[Figure | None, ChartSpec]`
- [x] Test với kết quả từ pipeline Text-to-SQL

### 4.3 Module Insight Generation (Tóm tắt chỉ số) ⏱️ _~4 giờ_ `Hoàn thành`

- [x] Tạo module `src/models/insight_generator.py`
- [x] Cập nhật prompt `build_insight_prompt` trong `src/models/prompt_templates.py`:
  - [x] Input: câu hỏi gốc, SQL, thống kê tính sẵn, preview DataFrame
  - [x] Output: 3-5 bullet points insight bằng tiếng Việt
- [x] Implement `generate_insights(question, sql, df, llm_client, spec) -> InsightResult` (có fallback theo luật khi LLM lỗi)
- [x] Thêm tính toán thống kê cơ bản tự động (`compute_statistics`):
  - [x] Tổng, trung bình, trung vị, min, max, xu hướng
  - [x] So sánh nhóm (top, bottom, tỉ trọng top 1 / top 3)
  - [x] Phát hiện outlier (IQR)
- [x] Test output insight với nhiều dạng câu hỏi

### 4.4 Tích hợp & Test ⏱️ _~3 giờ_ `Hoàn thành`

- [x] Tích hợp `chart_classifier`, `chart_generator`, `insight_generator` vào pipeline
- [x] Cập nhật `TextToSQLPipeline.run()` / `QueryResult` trả về: `generated_sql`, `dataframe`, `chart`, `chart_spec`, `insights`, `timings_ms`
- [x] Test end-to-end với 10 câu hỏi đa dạng (`tests/test_week4_visualization.py`) + 3 câu hỏi live với Gemini thật
- [ ] Commit code (máy chưa cài Git)

**Kết quả test (20/11/2026):**
- Unit tests offline (Tuần 1–4): **153 passed** (`tests/test_week4_visualization.py` đóng góp 54 tests).
- Test live với `gemini-3.5-flash-lite` (3 câu hỏi, cache tắt): 3/3 thành công (Bar, Line, Pie), tổng thời gian end-to-end (SQL + DuckDB + Chart + Insight) chỉ **2.2s–2.7s/câu**.

> **Tổng thời gian ước tính Tuần 4:** ~17 giờ

---

## 🟢 TUẦN 5 — Giao diện Streamlit & Tích hợp hệ thống `Hoàn thành`

### 5.1 Thiết kế giao diện Streamlit ⏱️ _~5 giờ_ `Hoàn thành`

- [x] Cài đặt `streamlit` (`1.66.0`)
- [x] Tạo file `app.py` (entry point), `src/ui/services.py`, `src/ui/styles.py` và `.streamlit/config.toml`
- [x] Thiết kế layout chính theo phong cách BI/Analytics:
  - [x] **Header**: Hero badges, gradient title, mô tả ngắn và thanh chuyển 3 không gian làm việc (`st.segmented_control`)
  - [x] **Sidebar**: thẻ thương hiệu & trạng thái DB, cấu hình AI (model, cache, insight, max corrections), 8 câu hỏi gợi ý, lịch sử câu hỏi, tóm tắt & JSON metrics Self-Correction
  - [x] **Main area**: 3 không gian — Hỏi đáp Phân tích (Welcome Dashboard 4 KPI sống + sơ đồ 5 bước + thẻ gợi ý 2×2), Star Schema & Dữ liệu (sơ đồ 6 bảng, từ điển cột, xem trước 10 dòng), Hệ thống & Hiệu năng (metrics, 6 lớp SQL Guardrails, nhật ký & biểu đồ độ trễ phiên)
- [x] Thiết kế khu vực hiển thị kết quả (`st.tabs`):
  - [x] Tab 1: Biểu đồ (Plotly chart)
  - [x] Tab 2: Bảng dữ liệu (DataFrame)
  - [x] Tab 3: SQL Query (syntax highlighted + lịch sử tự sửa)
  - [x] Tab 4: Insights (tóm tắt tiếng Việt)
- [x] Thêm câu hỏi gợi ý (8 example questions) click để chạy trực tiếp

### 5.2 Tích hợp toàn diện các module ⏱️ _~5 giờ_ `Hoàn thành`

- [x] Kết nối `TextToSQLPipeline` với Streamlit (mặc định `gemini-3.5-flash-lite`)
- [x] Hiển thị loading state khi đang xử lý
- [x] Hiển thị tiến trình pipeline (`progress_callback` + `st.status`: sinh SQL → thực thi → biểu đồ → nhận xét)
- [x] Xử lý error states (thiếu API key, thiếu DB, lỗi bảo mật, timeout, lỗi Gemini)
- [x] Implement session state cho lịch sử hội thoại (`st.session_state.history`, nút xóa lịch sử)
- [x] Cache: dùng `@st.cache_resource` cho pipeline thay cho `@st.cache_data`, kết hợp cache phản hồi LLM trên đĩa (`cache/llm_responses/`)

### 5.3 Tối ưu hóa UX ⏱️ _~4 giờ_ `Hoàn thành`

- [x] Thêm status/spinner khi chờ kết quả
- [x] Responsive design (mobile-friendly) — _đã bổ sung CSS `@media (max-width: 900px)` và `600px` cho KPI grid, pipeline, Star Schema và Guardrails; đã kiểm trên desktop 1280×800, chưa kiểm trên thiết bị mobile thật_
- [x] Thêm nút "Copy SQL" (tích hợp sẵn trên `st.code`), "Tải CSV" (UTF-8 BOM), "Tải biểu đồ (HTML)"
- [x] Hiển thị thời gian xử lý từng bước và tổng latency (`st.metric`)
- [x] Dark/Light mode toggle — _dùng menu Settings tích hợp sẵn của Streamlit_
- [x] Keyboard shortcut (`Enter` để gửi câu hỏi qua `st.chat_input`)
- [x] Error handling cho edge cases (`validate_question`: câu hỏi rỗng, khoảng trắng, quá 500 ký tự)

### 5.4 Test giao diện ⏱️ _~3 giờ_ `Hoàn thành`

- [ ] Test trên trình duyệt Chrome, Firefox, Edge — _mới kiểm thử trên trình duyệt headless tích hợp sẵn; bỏ qua bước kiểm thử riêng lẻ từng trình duyệt_
- [x] Test các luồng sử dụng chính (happy path) — qua `AppTest` và trình duyệt thật tại `http://localhost:8501`
- [x] Test các luồng lỗi (error path) — thiếu API key, câu hỏi bảo mật/xóa dữ liệu, input rỗng/quá dài
- [x] Fix UI bugs — dùng `width="stretch"` thay `use_container_width` để tương thích Streamlit 1.66 không cảnh báo
- [ ] Commit code — _máy chưa cài `git`, bỏ qua bước commit_

**Kết quả test (24/11/2026):**
- Unit tests offline (Tuần 1–5): **172 passed** (`tests/test_week5_ui.py` đóng góp 19 tests gồm kiểm thử XSS escaping, tổng quan DB, schema explorer và chuyển 3 không gian `AppTest`; lọc bỏ 2 test tích hợp gọi API thật ở Tuần 2).
- Kiểm thử trình duyệt thật tại `http://localhost:8502`: xác nhận đầy đủ Welcome Dashboard (4 thẻ KPI sống từ DuckDB, sơ đồ 5 bước, 4 thẻ nhanh), không gian `Star Schema & Dữ liệu` (6 bảng + xem trước dữ liệu), không gian `Hệ thống & Hiệu năng` (metrics + 6 thẻ Guardrails) và luồng hỏi `"Top 5 danh mục sản phẩm có doanh thu cao nhất?"` với thẻ kết quả mới (banner, pill metadata, Tóm tắt nhanh, 4 tab + thống kê Pandas). Đã sửa lỗi xuống dòng ở thẻ thương hiệu sidebar và thẻ KPI thứ 4.

> **Tổng thời gian ước tính Tuần 5:** ~17 giờ

---

## 🟢 TUẦN 6 — Kiểm thử & Đánh giá hiệu năng `Hoàn thành`

### 6.1 Xây dựng bộ kiểm thử ⏱️ _~5 giờ_ `Hoàn thành`

- [x] Tạo file `tests/test_questions.json` với 40 câu hỏi
- [x] Phân loại câu hỏi theo độ khó:
  - [x] **Dễ (12 câu)**: đếm, tổng, trung bình, filter đơn giản (`E01`–`E12`)
  - [x] **Trung bình (12 câu)**: GROUP BY, ORDER BY, filter, JOIN (`M01`–`M12`)
  - [x] **Khó (11 câu)**: CTE, Window Function (`LAG`, `ROW_NUMBER`, `SUM OVER`), subquery, `HAVING`, multi-JOIN (`H01`–`H11`)
  - [x] **Edge cases (5 câu)**: SQL injection/DML (`X01`–`X03`), ngoài schema (`X04`), kết quả rỗng (`X05`)
- [x] Viết SQL đáp án (`ground_truth_sql` và `alt_ground_truth_sql`) cho từng câu hỏi
- [x] Xác thực và điền kết quả kỳ vọng (`expected_row_count`, `expected_preview`) trực tiếp trên DuckDB qua `python run_benchmark.py --populate-expected`

### 6.2 Chạy thực nghiệm & Đo đạc ⏱️ _~6 giờ_ `Hoàn thành`

- [x] Tạo script `run_benchmark.py`, `src/evaluation/evaluator.py` và `tests/test_week6_benchmark.py`
- [x] Đo **Execution Accuracy (EX)**:
  - [x] So sánh kết quả truy vấn LLM vs. ground truth (`compare_dataframes` hỗ trợ ngưỡng sai số và cột phụ kiểu BIRD)
  - [x] Tính tỉ lệ chính xác theo từng mức độ khó
  - [x] Tính tỉ lệ chính xác tổng thể
- [x] Đo **Latency**:
  - [x] Thời gian sinh SQL (LLM response time)
  - [x] Thời gian thực thi SQL + Guardrails (DuckDB execution time)
  - [x] Tổng thời gian end-to-end
  - [x] P50, P90, P99 latency (`compute_latency_stats`)
- [x] So sánh hiệu quả **Self-Correction**:
  - [x] Chạy test suite KHÔNG có self-correction (`max_corrections=0`) → **33/35 (94.3%)** EX
  - [x] Chạy test suite CÓ self-correction (`max_corrections=3`) → **34/35 (97.1%)** EX
  - [x] Tính % cải thiện (`+2.85` điểm %) & tách rõ nguyên nhân (tính không tất định ở câu `M06`, `triggered_count = 0` do lần chạy không phát sinh lỗi SQL; khả năng tự sửa khi có lỗi đã kiểm chứng ở Tuần 3)
  - [x] Phân tích chi tiết loại lỗi ở cả lần chạy thử đầu dính 429 và lần chạy sạch `--delay 3.2s`

### 6.3 Phân tích kết quả & Báo cáo ⏱️ _~4 giờ_ `Hoàn thành`

- [x] Tạo bảng tổng hợp kết quả thực nghiệm (`results/BENCHMARK_REPORT.md`, `results/benchmark_summary.csv`)
- [x] Vẽ biểu đồ so sánh (`accuracy_by_difficulty.html`, `latency_distribution.html`, `error_breakdown.html`)
- [x] Phân tích lỗi: phân loại các câu hỏi thất bại (`H09`, `X03`, `X04` ở lượt chính; `M06` ở baseline)
  - [x] Lỗi do LLM hiểu sai câu hỏi (`X04`, `X03`)
  - [x] Lỗi do schema / so khớp nhãn (`H09`)
  - [x] Lỗi do SQL syntax (`sql_syntax`)
- [x] Ghi nhận hạn chế và hướng cải thiện
- [x] Lưu kết quả vào thư mục `results/`
- [ ] Commit code & kết quả — _máy chưa cài `git`, bỏ qua bước commit_

**Kết quả thực nghiệm thật (24/11/2026 — `gemini-3.5-flash-lite`, `LLM_CACHE=False`, `--delay 3.2s` tránh giới hạn 15 RPM Free Tier):**
- **Execution Accuracy (35 câu chuẩn E+M+H):**
  - Không Self-Correction (`max_corrections=0`): **33/35 (94.3%)** — Easy `12/12` (100%), Medium `11/12` (91.7%), Hard `10/11` (90.9%); Edge: `3/5` (60.0%).
  - Có Self-Correction (`max_corrections=3`): **34/35 (97.1%)** — Easy `12/12` (100%), Medium `12/12` (100%), Hard `10/11` (90.9%); Edge: `3/5` (60.0%).
- **Latency (`with_correction`):** End-to-End Mean **1.32s**, P50 **1.30s**, P90 **1.53s**, P99 **1.70s** (Sinh SQL Mean 1.24s; DuckDB + Guardrails Mean 80.6ms).
- **Unit tests offline (Tuần 1–6):** **178 passed** (`tests/test_week6_benchmark.py` đóng góp 6 tests).

> **Tổng thời gian ước tính Tuần 6:** ~15 giờ

---

## ⚪ TUẦN 7 — Viết báo cáo đồ án `Chưa bắt đầu`

### 7.1 Viết nội dung báo cáo ⏱️ _~14 giờ_

- [ ] **Chương 1: Giới thiệu** (~2 giờ)
  - [ ] Đặt vấn đề và tính cấp thiết
  - [ ] Mục tiêu đề tài
  - [ ] Phạm vi nghiên cứu
  - [ ] Phương pháp nghiên cứu
  - [ ] Cấu trúc báo cáo
- [ ] **Chương 2: Cơ sở lý thuyết** (~3 giờ)
  - [ ] Tổng quan Text-to-SQL
  - [ ] Large Language Models (LLM) và Gemini
  - [ ] Prompt Engineering: Schema Linking, Few-shot, CoT
  - [ ] Star Schema và Data Warehouse
  - [ ] Các nghiên cứu liên quan (Related Work)
- [ ] **Chương 3: Phân tích & Thiết kế hệ thống** (~3 giờ)
  - [ ] Kiến trúc tổng thể hệ thống
  - [ ] Thiết kế cơ sở dữ liệu (Star Schema)
  - [ ] Thiết kế module Text-to-SQL Pipeline
  - [ ] Thiết kế module SQL Guardrails & Self-Correction
  - [ ] Thiết kế module Auto Visualization
  - [ ] Thiết kế giao diện người dùng
- [ ] **Chương 4: Cài đặt & Thực nghiệm** (~3 giờ)
  - [ ] Môi trường cài đặt (Python, thư viện, phần cứng)
  - [ ] Chi tiết cài đặt từng module
  - [ ] Kết quả thực nghiệm (bảng, biểu đồ)
  - [ ] Phân tích và đánh giá kết quả
  - [ ] So sánh có/không Self-Correction
- [ ] **Chương 5: Kết luận** (~1 giờ)
  - [ ] Tóm tắt kết quả đạt được
  - [ ] Hạn chế
  - [ ] Hướng phát triển tương lai
- [ ] Viết **Tóm tắt (Abstract)** tiếng Việt và tiếng Anh (~1 giờ)
- [ ] Viết **Lời cảm ơn** (~0.5 giờ)

### 7.2 Rà soát tài liệu tham khảo ⏱️ _~3 giờ_

- [ ] Thu thập danh sách tài liệu tham khảo (ít nhất 15-20 nguồn)
  - [ ] Bài báo khoa học về Text-to-SQL (Spider, BIRD, DIN-SQL, DAIL-SQL, ...)
  - [ ] Tài liệu về LLM và Prompt Engineering
  - [ ] Tài liệu kỹ thuật (DuckDB, Streamlit, Plotly)
- [ ] Định dạng tài liệu tham khảo theo chuẩn (IEEE hoặc APA)
- [ ] Kiểm tra tất cả trích dẫn trong bài đã có trong danh mục

### 7.3 Rà soát & Chỉnh sửa ⏱️ _~3 giờ_

- [ ] Kiểm tra chính tả và ngữ pháp
- [ ] Kiểm tra format (font, size, heading, numbering)
- [ ] Kiểm tra hình ảnh, bảng biểu, caption
- [ ] Kiểm tra mục lục, danh mục hình, danh mục bảng
- [ ] Xuất file PDF

> **Tổng thời gian ước tính Tuần 7:** ~20 giờ

---

## ⚪ TUẦN 8 — Đóng gói, Slide & Video demo `Chưa bắt đầu`

### 8.1 Đóng gói mã nguồn ⏱️ _~3 giờ_

- [ ] Dọn dẹp code: xóa file thừa, comment debug, code tạm
- [ ] Chuẩn hóa cấu trúc thư mục dự án:
  ```
  DACS4/
  ├── app.py
  ├── config.py
  ├── requirements.txt
  ├── README.md
  ├── .env.example
  ├── data/
  │   ├── raw/
  │   └── olist.duckdb
  ├── modules/
  │   ├── text_to_sql.py
  │   ├── sql_guardrails.py
  │   ├── self_correction.py
  │   ├── chart_classifier.py
  │   ├── chart_generator.py
  │   └── insight_generator.py
  ├── prompts/
  ├── tests/
  └── results/
  ```
- [ ] Tạo/cập nhật `requirements.txt` (hoặc `pyproject.toml`)
- [ ] Viết `README.md` hoàn chỉnh:
  - [ ] Giới thiệu dự án
  - [ ] Screenshots / GIFs
  - [ ] Hướng dẫn cài đặt (step-by-step)
  - [ ] Hướng dẫn sử dụng
  - [ ] Cấu trúc thư mục
  - [ ] Tech stack
  - [ ] Kết quả thực nghiệm tóm tắt
  - [ ] License
- [ ] Tạo file `.env.example`
- [ ] Test cài đặt từ đầu trên máy sạch (hoặc venv mới)

### 8.2 Soạn slide thuyết trình ⏱️ _~5 giờ_

- [ ] Xác định nội dung và số lượng slide (~15-20 slides)
- [ ] Slide nội dung:
  - [ ] Slide 1: Trang bìa
  - [ ] Slide 2: Nội dung trình bày
  - [ ] Slide 3-4: Đặt vấn đề & Mục tiêu
  - [ ] Slide 5-6: Cơ sở lý thuyết (Text-to-SQL, LLM, Prompt Engineering)
  - [ ] Slide 7-9: Kiến trúc hệ thống & Thiết kế
  - [ ] Slide 10-13: Demo & Kết quả thực nghiệm
  - [ ] Slide 14-15: Kết luận & Hướng phát triển
  - [ ] Slide 16: Q&A
- [ ] Thiết kế slide đẹp, chuyên nghiệp
- [ ] Thêm hình ảnh minh họa, sơ đồ kiến trúc
- [ ] Chuẩn bị speaker notes
- [ ] Tập trình bày (dry run) 1-2 lần

### 8.3 Quay video demo ⏱️ _~4 giờ_

- [ ] Viết kịch bản video demo (~3-5 phút)
  - [ ] Giới thiệu ngắn gọn
  - [ ] Demo nhập câu hỏi → hiển thị SQL → kết quả → biểu đồ → insight
  - [ ] Demo 3-5 câu hỏi đa dạng (dễ → khó)
  - [ ] Demo tính năng self-correction (cố tình hỏi câu khó)
  - [ ] Kết luận
- [ ] Chuẩn bị môi trường quay (dọn desktop, chạy app)
- [ ] Quay video (OBS Studio hoặc công cụ tương tự)
- [ ] Chỉnh sửa video (cắt ghép, thêm text overlay nếu cần)
- [ ] Xuất video MP4, kiểm tra chất lượng

### 8.4 Kiểm tra cuối cùng ⏱️ _~2 giờ_

- [ ] Review toàn bộ deliverables:
  - [ ] ✅ Mã nguồn hoàn chỉnh trên GitHub
  - [ ] ✅ README.md chi tiết
  - [ ] ✅ Báo cáo đồ án (PDF)
  - [ ] ✅ Slide thuyết trình
  - [ ] ✅ Video demo
- [ ] Backup toàn bộ dự án
- [ ] Nộp bài

> **Tổng thời gian ước tính Tuần 8:** ~14 giờ

---

## 📝 GHI CHÚ

- **Ký hiệu trạng thái:**
  - ⚪ Chưa bắt đầu
  - 🟡 Đang thực hiện
  - 🟢 Hoàn thành
  - 🔴 Bị chặn / Cần hỗ trợ

- **Cách cập nhật:**
  - Đánh dấu `[x]` khi hoàn thành task
  - Cập nhật % hoàn thành trong bảng tổng quan
  - Ghi chú vấn đề gặp phải bên dưới mỗi tuần

- **Tổng thời gian ước tính toàn dự án:** ~136 giờ (~17 giờ/tuần)

---

> _Tài liệu này được tạo tự động và cần được cập nhật thủ công theo tiến độ thực tế._
