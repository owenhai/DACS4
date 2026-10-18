# 📊 DACS4 - TIẾN ĐỘ DỰ ÁN

> **Dự án:** Automated Data Insights Engine (Text-to-SQL + LLM)  
> **Thời gian:** 8 tuần  
> **Cập nhật lần cuối:** _ngày/tháng/năm_

---

## 📈 TỔNG QUAN TIẾN ĐỘ

| Tuần | Nội dung chính | Trạng thái | Hoàn thành |
|:----:|----------------|:----------:|:----------:|
| 1 | Thu thập & Xử lý dữ liệu, Star Schema, DuckDB | 🟢 Hoàn thành | ▓▓▓▓▓▓▓▓▓▓ 100% |
| 2 | Tích hợp Gemini Flash, Prompt Engineering, Text-to-SQL | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 3 | SQL Guardrails & Self-Correction Loop | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 4 | Auto Visualization & Insight Generation | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 5 | Giao diện Streamlit & Tích hợp hệ thống | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 6 | Kiểm thử & Đánh giá hiệu năng | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 7 | Viết báo cáo đồ án | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 8 | Đóng gói, Slide & Video demo | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |

**Tiến độ tổng thể:** ▓░░░░░░░░░ **12%**

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
  - [ ] Các cột: `zip_code_prefix`, `lat`, `lng`, `city`, `state`

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

## ⚪ TUẦN 2 — Tích hợp Gemini Flash & Pipeline Text-to-SQL `Chưa bắt đầu`

### 2.1 Cấu hình môi trường & Google GenAI SDK ⏱️ _~2 giờ_

- [ ] Tạo tài khoản Google AI Studio và lấy API Key
- [ ] Cài đặt thư viện `google-genai` (Google GenAI SDK)
- [ ] Thiết lập file `.env` lưu `GOOGLE_API_KEY`
- [ ] Viết module `config.py` đọc biến môi trường
- [ ] Test kết nối cơ bản với Gemini Flash (`gemini-2.0-flash`)
- [ ] Xác nhận rate limits và pricing tier

### 2.2 Thiết kế Prompt Template ⏱️ _~5 giờ_

- [ ] Nghiên cứu các kỹ thuật prompt engineering cho Text-to-SQL
  - [ ] Schema Linking: gắn schema vào prompt
  - [ ] Few-shot Prompting: cung cấp ví dụ câu hỏi → SQL
  - [ ] Chain-of-Thought: yêu cầu LLM giải thích logic trước khi viết SQL
- [ ] Xây dựng System Prompt chính
  - [ ] Mô tả vai trò của LLM (SQL expert)
  - [ ] Nhúng schema metadata vào prompt
  - [ ] Quy tắc viết SQL (chỉ SELECT, dùng alias, format chuẩn)
  - [ ] Ràng buộc output format (chỉ trả SQL, không markdown)
- [ ] Tạo bộ Few-shot Examples (10-15 cặp câu hỏi/SQL)
  - [ ] Ví dụ đơn giản: đếm, tổng, trung bình
  - [ ] Ví dụ trung bình: GROUP BY, ORDER BY, HAVING
  - [ ] Ví dụ nâng cao: subquery, window function, nhiều JOIN
- [ ] Lưu template trong `prompts/` directory
- [ ] Test thủ công prompt với 5 câu hỏi khác nhau

### 2.3 Xây dựng Pipeline Text-to-SQL cơ bản ⏱️ _~6 giờ_

- [ ] Tạo module `text_to_sql.py`
- [ ] Viết class `TextToSQLPipeline`:
  - [ ] `__init__()`: khởi tạo GenAI client, load schema metadata
  - [ ] `build_prompt(user_question: str) -> str`: ghép prompt từ template + câu hỏi
  - [ ] `generate_sql(user_question: str) -> str`: gọi Gemini Flash, trả về SQL
  - [ ] `execute_sql(sql: str) -> pd.DataFrame`: thực thi SQL trên DuckDB
  - [ ] `run(user_question: str) -> dict`: pipeline end-to-end
- [ ] Xử lý response parsing: trích xuất SQL từ response LLM
- [ ] Thêm logging chi tiết (câu hỏi → prompt → SQL → kết quả)
- [ ] Xử lý timeout và retry logic cho API calls

### 2.4 Test & Debug Pipeline ⏱️ _~4 giờ_

- [ ] Chạy thử 10 câu hỏi cơ bản, ghi nhận kết quả
- [ ] Phân tích các trường hợp lỗi phổ biến
- [ ] Điều chỉnh prompt dựa trên kết quả test
- [ ] Đo thời gian phản hồi trung bình (latency baseline)
- [ ] Commit code & cập nhật tài liệu

> **Tổng thời gian ước tính Tuần 2:** ~17 giờ

---

## ⚪ TUẦN 3 — SQL Guardrails & Self-Correction Loop `Chưa bắt đầu`

### 3.1 Xây dựng module SQL Guardrails ⏱️ _~5 giờ_

- [ ] Cài đặt thư viện `sqlparse`
- [ ] Tạo module `sql_guardrails.py`
- [ ] Implement các bộ lọc bảo mật:
  - [ ] **Whitelist kiểm tra**: chỉ cho phép `SELECT` statements
  - [ ] **Blacklist từ khóa**: chặn `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`
  - [ ] **Chặn comment injection**: loại bỏ `--`, `/* */`
  - [ ] **Giới hạn độ phức tạp**: số lượng JOIN tối đa, subquery depth
  - [ ] **Kiểm tra tên bảng/cột**: chỉ cho phép bảng/cột có trong schema
- [ ] Viết hàm `validate_sql(sql: str) -> ValidationResult`
  - [ ] Trả về `is_valid`, `error_message`, `sanitized_sql`
- [ ] Viết hàm `sanitize_sql(sql: str) -> str`
  - [ ] Loại bỏ LIMIT nếu cần, thêm LIMIT mặc định
  - [ ] Format lại SQL cho dễ đọc
- [ ] Unit tests cho tất cả các trường hợp bảo mật

### 3.2 Xây dựng Self-Correction Loop ⏱️ _~6 giờ_

- [ ] Thiết kế luồng tự sửa lỗi:
  ```
  Câu hỏi → SQL → Validate → Execute → Nếu lỗi → Gửi lỗi cho LLM → SQL mới → Lặp lại (tối đa 3 lần)
  ```
- [ ] Tạo module `self_correction.py`
- [ ] Implement `SelfCorrectionLoop`:
  - [ ] `attempt_execution(sql: str) -> ExecutionResult`: thực thi và bắt lỗi
  - [ ] `build_correction_prompt(original_question, failed_sql, error_msg) -> str`: tạo prompt sửa lỗi
  - [ ] `run_with_correction(question: str, max_retries: int = 3) -> dict`: vòng lặp chính
- [ ] Xử lý các loại lỗi phổ biến:
  - [ ] Lỗi cú pháp SQL (syntax error)
  - [ ] Lỗi tên bảng/cột không tồn tại
  - [ ] Lỗi kiểu dữ liệu không tương thích
  - [ ] Lỗi timeout (query quá chậm)
  - [ ] Kết quả rỗng (empty result)
- [ ] Logging chi tiết: ghi lại từng lần thử và lỗi
- [ ] Đo metrics: số lần retry trung bình, tỉ lệ sửa thành công

### 3.3 Tích hợp vào Pipeline chính ⏱️ _~3 giờ_

- [ ] Tích hợp `sql_guardrails` vào `TextToSQLPipeline`
- [ ] Tích hợp `self_correction` vào `TextToSQLPipeline`
- [ ] Cập nhật hàm `run()` với luồng: validate → execute → correct (nếu cần)
- [ ] Test end-to-end với 15 câu hỏi (gồm cả câu cố tình gây lỗi)
- [ ] Commit code & cập nhật tài liệu

### 3.4 Kiểm thử bảo mật ⏱️ _~2 giờ_

- [ ] Tạo bộ test SQL injection attempts
- [ ] Test với các prompt cố tình yêu cầu xóa/sửa dữ liệu
- [ ] Xác nhận tất cả đều bị chặn
- [ ] Ghi nhận kết quả vào báo cáo kiểm thử

> **Tổng thời gian ước tính Tuần 3:** ~16 giờ

---

## ⚪ TUẦN 4 — Auto Visualization & Insight Generation `Chưa bắt đầu`

### 4.1 Xây dựng thuật toán phân loại biểu đồ ⏱️ _~5 giờ_

- [ ] Tạo module `chart_classifier.py`
- [ ] Phân tích đặc điểm dữ liệu đầu ra để chọn biểu đồ:
  - [ ] **1 cột categorical + 1 cột numeric** → Bar Chart
  - [ ] **1 cột datetime + 1 cột numeric** → Line Chart
  - [ ] **1 cột categorical + 1 cột numeric (tỉ lệ)** → Pie Chart
  - [ ] **2 cột numeric** → Scatter Plot
  - [ ] **1 cột numeric (phân phối)** → Histogram
  - [ ] **Nhiều cột categorical + numeric** → Grouped/Stacked Bar
  - [ ] **Dữ liệu có lat/lng** → Map
  - [ ] **Bảng nhỏ (≤ 10 rows)** → Table (hiển thị trực tiếp)
- [ ] Viết hàm `classify_chart_type(df: pd.DataFrame, sql: str) -> ChartType`
- [ ] Viết hàm `detect_column_roles(df: pd.DataFrame) -> dict`
  - [ ] Phân biệt: categorical, numeric, datetime, geographic
- [ ] Unit tests với nhiều dạng DataFrame khác nhau

### 4.2 Tích hợp Plotly Express ⏱️ _~5 giờ_

- [ ] Cài đặt `plotly`
- [ ] Tạo module `chart_generator.py`
- [ ] Implement từng loại biểu đồ:
  - [ ] `create_bar_chart(df, x_col, y_col, title) -> Figure`
  - [ ] `create_line_chart(df, x_col, y_col, title) -> Figure`
  - [ ] `create_pie_chart(df, names_col, values_col, title) -> Figure`
  - [ ] `create_scatter_plot(df, x_col, y_col, title) -> Figure`
  - [ ] `create_histogram(df, col, title) -> Figure`
  - [ ] `create_grouped_bar(df, x_col, y_col, color_col, title) -> Figure`
- [ ] Thiết kế theme/style thống nhất cho tất cả biểu đồ
  - [ ] Color palette, font, layout
- [ ] Hàm tổng hợp `auto_generate_chart(df, sql, question) -> Figure`
- [ ] Test với kết quả từ pipeline Text-to-SQL

### 4.3 Module Insight Generation (Tóm tắt chỉ số) ⏱️ _~4 giờ_

- [ ] Tạo module `insight_generator.py`
- [ ] Viết prompt cho LLM tóm tắt kết quả truy vấn:
  - [ ] Input: câu hỏi gốc, SQL, DataFrame kết quả
  - [ ] Output: 3-5 bullet points insight bằng tiếng Việt
- [ ] Implement `generate_insights(question, sql, df) -> str`
- [ ] Thêm tính toán thống kê cơ bản tự động:
  - [ ] Tổng, trung bình, min, max, xu hướng
  - [ ] So sánh (nếu có nhóm)
  - [ ] Phát hiện outlier đơn giản
- [ ] Test output insight với nhiều dạng câu hỏi

### 4.4 Tích hợp & Test ⏱️ _~3 giờ_

- [ ] Tích hợp `chart_classifier`, `chart_generator`, `insight_generator` vào pipeline
- [ ] Cập nhật `TextToSQLPipeline.run()` trả về: `sql`, `dataframe`, `chart`, `insights`
- [ ] Test end-to-end với 10 câu hỏi đa dạng
- [ ] Commit code

> **Tổng thời gian ước tính Tuần 4:** ~17 giờ

---

## ⚪ TUẦN 5 — Giao diện Streamlit & Tích hợp hệ thống `Chưa bắt đầu`

### 5.1 Thiết kế giao diện Streamlit ⏱️ _~5 giờ_

- [ ] Cài đặt `streamlit`
- [ ] Tạo file `app.py` (entry point)
- [ ] Thiết kế layout chính:
  - [ ] **Header**: logo, tên dự án, mô tả ngắn
  - [ ] **Sidebar**: cấu hình, lịch sử câu hỏi, câu hỏi gợi ý
  - [ ] **Main area**: ô nhập câu hỏi, kết quả
- [ ] Thiết kế khu vực hiển thị kết quả:
  - [ ] Tab 1: Bảng dữ liệu (DataFrame)
  - [ ] Tab 2: Biểu đồ (Plotly chart)
  - [ ] Tab 3: SQL Query (syntax highlighted)
  - [ ] Tab 4: Insights (tóm tắt)
- [ ] Thêm câu hỏi gợi ý (example questions) click-to-fill

### 5.2 Tích hợp toàn diện các module ⏱️ _~5 giờ_

- [ ] Kết nối `TextToSQLPipeline` với Streamlit
- [ ] Hiển thị loading state khi đang xử lý
- [ ] Hiển thị tiến trình pipeline (generating SQL → executing → charting)
- [ ] Xử lý error states (hiển thị lỗi thân thiện)
- [ ] Implement session state cho lịch sử hội thoại
- [ ] Cache kết quả để tránh gọi API trùng lặp (`@st.cache_data`)

### 5.3 Tối ưu hóa UX ⏱️ _~4 giờ_

- [ ] Thêm animation/spinner khi chờ kết quả
- [ ] Responsive design (mobile-friendly)
- [ ] Thêm nút "Copy SQL", "Download CSV", "Download Chart"
- [ ] Hiển thị thời gian xử lý (latency)
- [ ] Dark/Light mode toggle (nếu có thời gian)
- [ ] Keyboard shortcut (Enter để gửi câu hỏi)
- [ ] Error handling cho edge cases (câu hỏi rỗng, quá dài, v.v.)

### 5.4 Test giao diện ⏱️ _~3 giờ_

- [ ] Test trên trình duyệt Chrome, Firefox, Edge
- [ ] Test các luồng sử dụng chính (happy path)
- [ ] Test các luồng lỗi (error path)
- [ ] Fix UI bugs
- [ ] Commit code

> **Tổng thời gian ước tính Tuần 5:** ~17 giờ

---

## ⚪ TUẦN 6 — Kiểm thử & Đánh giá hiệu năng `Chưa bắt đầu`

### 6.1 Xây dựng bộ kiểm thử ⏱️ _~5 giờ_

- [ ] Tạo file `tests/test_questions.json` với 30-50 câu hỏi
- [ ] Phân loại câu hỏi theo độ khó:
  - [ ] **Dễ (10-15 câu)**: đếm, tổng, trung bình đơn giản
    - Ví dụ: "Có bao nhiêu đơn hàng?", "Doanh thu tổng cộng là bao nhiêu?"
  - [ ] **Trung bình (10-15 câu)**: GROUP BY, ORDER BY, filter, nhiều bảng
    - Ví dụ: "Top 10 danh mục sản phẩm bán chạy nhất?", "Doanh thu theo tháng?"
  - [ ] **Khó (10-15 câu)**: subquery, window function, tính toán phức tạp
    - Ví dụ: "Tỉ lệ tăng trưởng doanh thu so với tháng trước?", "Phân tích RFM khách hàng?"
  - [ ] **Edge cases (5 câu)**: câu hỏi mơ hồ, không liên quan, injection
- [ ] Viết SQL đáp án (ground truth) cho mỗi câu hỏi
- [ ] Viết kết quả kỳ vọng (expected results) cho mỗi câu

### 6.2 Chạy thực nghiệm & Đo đạc ⏱️ _~6 giờ_

- [ ] Tạo script `run_benchmark.py` chạy tự động toàn bộ test suite
- [ ] Đo **Execution Accuracy (EX)**:
  - [ ] So sánh kết quả truy vấn LLM vs. ground truth
  - [ ] Tính tỉ lệ chính xác theo từng mức độ khó
  - [ ] Tính tỉ lệ chính xác tổng thể
- [ ] Đo **Latency**:
  - [ ] Thời gian sinh SQL (LLM response time)
  - [ ] Thời gian thực thi SQL (DuckDB execution time)
  - [ ] Tổng thời gian end-to-end
  - [ ] P50, P90, P99 latency
- [ ] So sánh hiệu quả **Self-Correction**:
  - [ ] Chạy test suite KHÔNG có self-correction → ghi nhận accuracy
  - [ ] Chạy test suite CÓ self-correction → ghi nhận accuracy
  - [ ] Tính % cải thiện nhờ self-correction
  - [ ] Phân tích chi tiết: loại lỗi nào được sửa thành công

### 6.3 Phân tích kết quả & Báo cáo ⏱️ _~4 giờ_

- [ ] Tạo bảng tổng hợp kết quả thực nghiệm
- [ ] Vẽ biểu đồ so sánh (accuracy by difficulty, latency distribution)
- [ ] Phân tích lỗi: phân loại các câu hỏi thất bại
  - [ ] Lỗi do LLM hiểu sai câu hỏi
  - [ ] Lỗi do schema phức tạp
  - [ ] Lỗi do SQL syntax
- [ ] Ghi nhận hạn chế và hướng cải thiện
- [ ] Lưu kết quả vào `results/` directory
- [ ] Commit code & kết quả

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
