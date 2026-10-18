# ĐỀ CƯƠNG ĐỒ ÁN CƠ SỞ 4 (DACS4)

**Tên sinh viên:** Lê Đức Hải  
**Định hướng nghề nghiệp:** Data Analyst / Data Scientist (DA/DS)  
**Thời gian thực hiện:** 8 tuần (Dự kiến 1–2 giờ/ngày)  

---

## 1. Tên đề tài
**Nghiên cứu và xây dựng hệ thống phân tích dữ liệu thông minh kết hợp kỹ thuật Text-to-SQL và Mô hình ngôn ngữ lớn (Automated Data Insights Engine)**

---

## 2. Mô tả tổng quan
* **Mô tả tổng quan đề tài:**  
  Trong bối cảnh ra quyết định dựa trên dữ liệu, việc trích xuất số liệu báo cáo thường gặp rào cản do đòi hỏi kỹ năng viết truy vấn SQL phức tạp, trong khi các dashboard tĩnh truyền thống lại thiếu linh hoạt trước các câu hỏi phân tích đột xuất (ad-hoc analytics). Đề tài nghiên cứu và xây dựng một hệ thống phân tích dữ liệu tự động khép kín: chuẩn hóa dữ liệu theo mô hình phân tích (OLAP), kết hợp pipeline Text-to-SQL có cơ chế kiểm duyệt và tự sửa lỗi (Self-Correction Loop). Người dùng chỉ cần đặt câu hỏi bằng ngôn ngữ tự nhiên, hệ thống sẽ tự động chuyển đổi thành câu truy vấn SQL an toàn, thực thi trên cơ sở dữ liệu dạng cột, trực quan hóa kết quả thành biểu đồ tương tác và tự động tóm tắt nhận xét xu hướng kinh doanh.

* **Mục tiêu dự kiến đạt được:**  
  * Xây dựng thành công quy trình xử lý dữ liệu và thiết kế lược đồ phân tích (Star Schema) tối ưu hóa truy vấn cho tập dữ liệu thương mại điện tử thực tế.
  * Tích hợp thành công mô hình ngôn ngữ lớn pre-trained (Gemini Flash) thông qua API, áp dụng kỹ thuật In-Context Learning (Schema Linking, Few-shot Prompting).
  * Phát triển cơ chế bảo vệ truy vấn (SQL Guardrails) và vòng lặp tự sửa lỗi cú pháp (Self-Correction Loop) nhằm nâng cao độ tin cậy và an toàn khi tương tác với CSDL.
  * Tự động hóa khâu chọn biểu đồ trực quan (Plotly) và sinh nhận xét số liệu (Insights Generation).
  * Thực hiện đánh giá thực nghiệm định lượng độ chính xác thực thi (Execution Accuracy) và độ trễ (Latency) trên tập câu hỏi kiểm thử chuẩn hóa.

* **Kết quả đề tài:**  
  * **Sản phẩm phần mềm:** Ứng dụng web dashboard tương tác (Streamlit) tích hợp đầy đủ luồng: Khung chat hỏi đáp tự nhiên $\rightarrow$ Hiển thị câu lệnh SQL được sinh $\rightarrow$ Bảng dữ liệu kết quả $\rightarrow$ Biểu đồ tương tác đa chiều $\rightarrow$ Đoạn văn tóm tắt insight.
  * **Cơ sở dữ liệu:** File cơ sở dữ liệu phân tích nhúng (DuckDB) đã được chuẩn hóa mô hình dữ liệu (Fact/Dimension) từ bộ dữ liệu thực tế.
  * **Báo cáo chuyên môn:** Báo cáo đồ án hoàn chỉnh bao gồm cơ sở lý thuyết, kiến trúc hệ thống, sơ đồ luồng dữ liệu, bảng số liệu thực nghiệm đo đạc độ chính xác và các trích dẫn tài liệu học thuật tin cậy.

---

## 3. Nội dung thực hiện (50% Data + 50% AI)

### Phần 1: Kỹ thuật & Mô hình hóa Dữ liệu (50% Data Engineering & Analytics)
* Thu thập, làm sạch và tiền xử lý bộ dữ liệu thương mại điện tử thực tế bằng `pandas`/`polars`.
* Thiết kế lược đồ đa chiều (Star Schema: phân tách rõ bảng Fact và các bảng Dimension) và nạp dữ liệu vào hệ quản trị CSDL phân tích dạng cột DuckDB.
* Xây dựng từ điển dữ liệu và mô tả lược đồ (Schema Metadata: tên bảng, kiểu dữ liệu, ràng buộc khóa ngoại, mẫu giá trị thực tế).
* Xây dựng các hàm thống kê mô tả, tính toán chỉ số đo lường hiệu suất (KPIs: tăng trưởng, doanh thu, phân bố danh mục).

### Phần 2: Ứng dụng Trí tuệ Nhân tạo & Tự động hóa Suy luận (50% AI & Automation)
* Kết nối và cấu hình mô hình nền tảng Gemini Flash qua Google GenAI SDK; thiết lập Structured Outputs (JSON Schema).
* Xây dựng luồng Text-to-SQL áp dụng kỹ thuật Schema Linking và Few-shot In-Context Learning.
* Triển khai module kiểm duyệt an toàn truy vấn bằng thư viện `sqlparse` (chỉ cấp phép câu lệnh `SELECT`, chặn các lệnh nguy hại `DROP`, `DELETE`, `ALTER`).
* Xây dựng thuật toán vòng lặp tự sửa lỗi (Self-Correction Loop): tự động bắt lỗi cú pháp/logic từ DuckDB và nạp ngược lại cho LLM tái sinh câu lệnh chính xác.
* Xây dựng thuật toán chọn loại biểu đồ phù hợp theo đặc tính dữ liệu trả về và module tự động tóm tắt nhận xét số liệu (Insight Generation).

### Phần 3: Tích hợp Giao diện & Đánh giá Thực nghiệm
* Dựng giao diện người dùng tương tác bằng Streamlit.
* Chuẩn bị bộ 30–50 câu hỏi kiểm thử phân cấp độ khó (Easy, Medium, Hard).
* Đo lường, phân tích hiệu năng hệ thống qua 2 chỉ số: Execution Accuracy (EX) và Query Latency; so sánh hiệu quả trước và sau khi kích hoạt cơ chế Self-Correction.

---

## 4. Kế hoạch thực hiện (8 tuần)

| Thời gian | Nội dung thực hiện |
| :--- | :--- |
| **Tuần thứ 1** | - Thu thập bộ dữ liệu thương mại điện tử thực tế (Olist E-Commerce Dataset).<br>- Làm sạch dữ liệu, xử lý giá trị khuyết thiếu và chuẩn hóa kiểu dữ liệu.<br>- Thiết kế lược đồ Star Schema (bảng Fact đơn hàng, bảng Dimension khách hàng, sản phẩm, thời gian).<br>- Nạp dữ liệu vào DuckDB và xây dựng file từ điển cấu trúc (Schema Metadata). |
| **Tuần thứ 2** | - Cấu hình môi trường, tích hợp Google GenAI SDK kết nối mô hình Gemini Flash.<br>- Thiết kế Prompt template kết hợp Schema Linking và các mẫu ví dụ (Few-shot prompting).<br>- Xây dựng pipeline Text-to-SQL cơ bản: nhận câu hỏi tiếng Việt $\rightarrow$ sinh truy vấn SQL $\rightarrow$ thực thi thử nghiệm trên DuckDB. |
| **Tuần thứ 3** | - Tích hợp thư viện `sqlparse` xây dựng module bảo mật SQL Guardrails (chặn các lệnh can thiệp cấu trúc dữ liệu).<br>- Lập trình cơ chế xử lý ngoại lệ và vòng lặp tự sửa lỗi (Self-Correction Loop) khi database trả về mã lỗi cú pháp hoặc sai tên cột. |
| **Tuần thứ 4** | - Xây dựng thuật toán phân loại dữ liệu đầu ra để tự động ánh xạ sang loại biểu đồ phù hợp (Bar chart, Line chart, Scatter plot).<br>- Tích hợp thư viện Plotly Express để trực quan hóa dữ liệu tương tác.<br>- Xây dựng module tóm tắt chỉ số tự động (Insight Generation) bằng LLM dựa trên kết quả thống kê. |
| **Tuần thứ 5** | - Dựng giao diện tương tác bằng Streamlit (khung chat tương tác, thẻ hiển thị SQL, bảng dữ liệu kết quả, khung vẽ biểu đồ Plotly).<br>- Tích hợp toàn diện các module thành một luồng khép kín từ UI đến Database.<br>- Tối ưu hóa trải nghiệm người dùng, xử lý các trạng thái chờ (loading spinner) và thông báo lỗi thân thiện. |
| **Tuần thứ 6** | - Xây dựng kịch bản kiểm thử gồm 30–50 câu hỏi phân loại theo độ khó (dựa trên chuẩn Spider/BIRD benchmark).<br>- Chạy thực nghiệm đo đạc 2 chỉ số: Execution Accuracy (tỷ lệ chạy đúng) và Latency (thời gian phản hồi).<br>- Ghi nhận số liệu so sánh hiệu quả cải thiện độ chính xác của cơ chế Self-Correction. |
| **Tuần thứ 7** | - Viết báo cáo đồ án: tổng quan lý thuyết, phân tích kiến trúc hệ thống, chi tiết thiết kế dữ liệu, thuật toán xử lý lỗi và trình bày các biểu đồ phân tích kết quả thực nghiệm.<br>- Rà soát các tài liệu tham khảo khoa học theo chuẩn trích dẫn. |
| **Tuần thứ 8** | - Đóng gói mã nguồn, viết file hướng dẫn cài đặt (`README.md`).<br>- Soạn slide báo cáo đồ án tóm lược các đóng góp kỹ thuật chính.<br>- Quay video demo kịch bản hoạt động của hệ thống dự phòng và tổng duyệt chuẩn bị bảo vệ trước hội đồng. |

---

## 5. Tài liệu tham khảo cốt lõi
1. **DIN-SQL (NeurIPS 2023):** *DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction*. (Cơ sở lý thuyết cho luồng phân rã bài toán và vòng lặp Self-Correction).
2. **DAIL-SQL (VLDB 2024):** *Text-to-SQL Empowered by Large Language Models: A Benchmark Evaluation*. (Cơ sở lý thuyết cho kỹ thuật Schema Representation và Few-shot Selection).
3. **BIRD Benchmark (NeurIPS 2023):** *Can LLM Already Serve as A Database Interface? A Big Bench for Large-Scale Database Grounded Text-to-SQLs*. (Phương pháp đánh giá chỉ số Execution Accuracy - EX).
4. **Spider Benchmark (EMNLP 2018):** *Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task*. (Phương pháp phân loại cấp độ khó của câu hỏi).
5. **DuckDB Paper (VLDB 2019):** *DuckDB: an Embeddable Analytical Database*. (Cơ sở lý thuyết về CSDL dạng cột nhúng cho phân tích).
6. **Kimball's Dimensional Modeling:** *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling (3rd Edition)*. (Phương pháp luận thiết kế Star Schema).