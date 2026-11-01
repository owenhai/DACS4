"""Module Prompt Templates cho pipeline Text-to-SQL.

Thiết kế prompt theo kỹ thuật:
- Schema Linking: Đưa metadata bảng/cột liên quan vào context
- Few-shot In-Context Learning: Cung cấp ví dụ câu hỏi -> SQL mẫu
- Task Decomposition: Hướng dẫn LLM phân tích câu hỏi trước khi viết SQL

Dựa trên phương pháp từ DIN-SQL (NeurIPS 2023) và DAIL-SQL (VLDB 2024).
"""

import logging
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ===========================================================================
# SYSTEM INSTRUCTION - Vai trò và quy tắc cho LLM
# ===========================================================================

SYSTEM_INSTRUCTION: str = """You are an expert SQL analyst for DuckDB. Your task is to convert natural language questions (in Vietnamese or English) into correct, optimized SQL queries for a Star Schema database of Brazilian E-Commerce data (Olist).

STRICT RULES:
1. Generate ONLY SELECT statements. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or any DDL/DML.
2. Use ONLY the tables and columns provided in the schema. Do not invent table or column names.
3. Always use proper JOIN syntax with explicit ON clauses. Join fact_orders to dimension tables using surrogate keys (customer_key, product_key, seller_key, date_key).
4. For monetary values, the currency is BRL (Brazilian Real).
5. Use DuckDB SQL dialect (supports standard SQL, window functions, CTEs, LIMIT, etc.).
6. When asked about "revenue" or "doanh thu", use SUM(price) or SUM(payment_value) as appropriate.
7. When asked about "number of orders" or "so don hang", use COUNT(DISTINCT order_id) since fact_orders has multiple rows per order.
8. Always handle NULL values appropriately (use COALESCE, IS NOT NULL filters when needed).
9. Return ONLY the SQL query, no explanation text.
10. Use meaningful column aliases for readability.
11. Round decimal results to 2 decimal places where appropriate using ROUND().
12. For date filtering, join with dim_date and filter on year, month, quarter columns.
13. When the question is about "top N", always include ORDER BY and LIMIT."""


# ===========================================================================
# FEW-SHOT EXAMPLES - Ví dụ câu hỏi -> SQL
# ===========================================================================

FEW_SHOT_EXAMPLES: list[dict[str, str]] = [
    # --- Easy: Truy vấn đơn giản ---
    {
        "difficulty": "easy",
        "question": "Tổng số đơn hàng trong hệ thống là bao nhiêu?",
        "sql": (
            "SELECT COUNT(DISTINCT order_id) AS total_orders\n"
            "FROM fact_orders;"
        ),
    },
    {
        "difficulty": "easy",
        "question": "Tổng doanh thu của toàn bộ hệ thống là bao nhiêu?",
        "sql": (
            "SELECT ROUND(SUM(price), 2) AS total_revenue\n"
            "FROM fact_orders;"
        ),
    },
    {
        "difficulty": "easy",
        "question": "Điểm đánh giá trung bình của khách hàng là bao nhiêu?",
        "sql": (
            "SELECT ROUND(AVG(review_score), 2) AS avg_review_score\n"
            "FROM fact_orders\n"
            "WHERE review_score IS NOT NULL;"
        ),
    },
    # --- Medium: JOIN + GROUP BY ---
    {
        "difficulty": "medium",
        "question": "Doanh thu theo từng bang của khách hàng, sắp xếp giảm dần?",
        "sql": (
            "SELECT c.customer_state,\n"
            "       ROUND(SUM(f.price), 2) AS total_revenue,\n"
            "       COUNT(DISTINCT f.order_id) AS total_orders\n"
            "FROM fact_orders f\n"
            "JOIN dim_customers c ON f.customer_key = c.customer_key\n"
            "GROUP BY c.customer_state\n"
            "ORDER BY total_revenue DESC;"
        ),
    },
    {
        "difficulty": "medium",
        "question": "Top 5 danh mục sản phẩm có doanh thu cao nhất?",
        "sql": (
            "SELECT p.product_category_name_english AS category,\n"
            "       ROUND(SUM(f.price), 2) AS total_revenue,\n"
            "       COUNT(DISTINCT f.order_id) AS order_count\n"
            "FROM fact_orders f\n"
            "JOIN dim_products p ON f.product_key = p.product_key\n"
            "WHERE p.product_category_name_english IS NOT NULL\n"
            "GROUP BY p.product_category_name_english\n"
            "ORDER BY total_revenue DESC\n"
            "LIMIT 5;"
        ),
    },
    {
        "difficulty": "medium",
        "question": "Số lượng đơn hàng theo tháng trong năm 2018?",
        "sql": (
            "SELECT d.month,\n"
            "       d.month_name,\n"
            "       COUNT(DISTINCT f.order_id) AS order_count\n"
            "FROM fact_orders f\n"
            "JOIN dim_date d ON f.date_key = d.date_key\n"
            "WHERE d.year = 2018\n"
            "GROUP BY d.month, d.month_name\n"
            "ORDER BY d.month;"
        ),
    },
    # --- Hard: Multi-JOIN + subquery/CTE ---
    {
        "difficulty": "hard",
        "question": "So sánh doanh thu và điểm đánh giá trung bình giữa các quý trong năm 2017 và 2018?",
        "sql": (
            "SELECT d.year,\n"
            "       d.quarter,\n"
            "       ROUND(SUM(f.price), 2) AS total_revenue,\n"
            "       COUNT(DISTINCT f.order_id) AS order_count,\n"
            "       ROUND(AVG(f.review_score), 2) AS avg_review\n"
            "FROM fact_orders f\n"
            "JOIN dim_date d ON f.date_key = d.date_key\n"
            "WHERE d.year IN (2017, 2018)\n"
            "  AND f.review_score IS NOT NULL\n"
            "GROUP BY d.year, d.quarter\n"
            "ORDER BY d.year, d.quarter;"
        ),
    },
    {
        "difficulty": "hard",
        "question": "Top 10 thành phố của người bán có doanh thu cao nhất, kèm theo số đơn hàng và điểm đánh giá trung bình?",
        "sql": (
            "SELECT s.seller_city,\n"
            "       s.seller_state,\n"
            "       ROUND(SUM(f.price), 2) AS total_revenue,\n"
            "       COUNT(DISTINCT f.order_id) AS order_count,\n"
            "       ROUND(AVG(f.review_score), 2) AS avg_review\n"
            "FROM fact_orders f\n"
            "JOIN dim_sellers s ON f.seller_key = s.seller_key\n"
            "WHERE f.review_score IS NOT NULL\n"
            "GROUP BY s.seller_city, s.seller_state\n"
            "ORDER BY total_revenue DESC\n"
            "LIMIT 10;"
        ),
    },
    {
        "difficulty": "hard",
        "question": "Tỷ lệ phần trăm đơn hàng theo phương thức thanh toán?",
        "sql": (
            "WITH total AS (\n"
            "    SELECT COUNT(DISTINCT order_id) AS total_orders\n"
            "    FROM fact_orders\n"
            ")\n"
            "SELECT f.payment_type,\n"
            "       COUNT(DISTINCT f.order_id) AS order_count,\n"
            "       ROUND(\n"
            "           COUNT(DISTINCT f.order_id) * 100.0 / t.total_orders, 2\n"
            "       ) AS percentage\n"
            "FROM fact_orders f\n"
            "CROSS JOIN total t\n"
            "WHERE f.payment_type IS NOT NULL\n"
            "GROUP BY f.payment_type, t.total_orders\n"
            "ORDER BY order_count DESC;"
        ),
    },
    {
        "difficulty": "hard",
        "question": "Thời gian giao hàng trung bình theo danh mục sản phẩm, chỉ lấy những danh mục có hơn 100 đơn?",
        "sql": (
            "SELECT p.product_category_name_english AS category,\n"
            "       COUNT(DISTINCT f.order_id) AS order_count,\n"
            "       ROUND(AVG(f.delivery_days), 1) AS avg_delivery_days,\n"
            "       ROUND(MIN(f.delivery_days), 1) AS min_delivery_days,\n"
            "       ROUND(MAX(f.delivery_days), 1) AS max_delivery_days\n"
            "FROM fact_orders f\n"
            "JOIN dim_products p ON f.product_key = p.product_key\n"
            "WHERE f.delivery_days IS NOT NULL\n"
            "  AND p.product_category_name_english IS NOT NULL\n"
            "GROUP BY p.product_category_name_english\n"
            "HAVING COUNT(DISTINCT f.order_id) > 100\n"
            "ORDER BY avg_delivery_days DESC;"
        ),
    },
]


# ===========================================================================
# PROMPT BUILDER - Xây dựng prompt hoàn chỉnh
# ===========================================================================

def build_text_to_sql_prompt(
    user_question: str,
    schema_text: str,
    num_examples: int = 5,
    include_decomposition: bool = True,
) -> str:
    """Xây dựng prompt hoàn chỉnh cho Text-to-SQL.

    Kết hợp Schema Linking + Few-shot Examples + Task Decomposition
    theo phương pháp DIN-SQL.

    Args:
        user_question: Câu hỏi của người dùng (tiếng Việt hoặc Anh).
        schema_text: Mô tả schema đã format (từ schema_metadata.format_schema_for_prompt).
        num_examples: Số ví dụ few-shot đưa vào (mặc định 5).
        include_decomposition: Có thêm bước phân tích câu hỏi không.

    Returns:
        Prompt hoàn chỉnh sẵn sàng gửi cho LLM.
    """
    sections: list[str] = []

    # --- Phần 1: Schema Context (Schema Linking) ---
    sections.append("=" * 60)
    sections.append("DATABASE SCHEMA")
    sections.append("=" * 60)
    sections.append(schema_text)
    sections.append("")

    # --- Phần 2: Few-shot Examples ---
    selected_examples = _select_examples(num_examples)

    sections.append("=" * 60)
    sections.append("EXAMPLE QUERIES")
    sections.append("=" * 60)
    sections.append("")

    for i, example in enumerate(selected_examples, 1):
        sections.append(f"Example {i} [{example['difficulty'].upper()}]:")
        sections.append(f"Question: {example['question']}")
        sections.append(f"SQL:\n{example['sql']}")
        sections.append("")

    # --- Phần 3: Task Decomposition (tùy chọn) ---
    if include_decomposition:
        sections.append("=" * 60)
        sections.append("TASK")
        sections.append("=" * 60)
        sections.append("")
        sections.append("Analyze the following question step by step:")
        sections.append("1. Identify which tables are needed")
        sections.append("2. Identify which columns to SELECT and which to filter/group by")
        sections.append("3. Determine the correct JOIN conditions")
        sections.append("4. Write the final SQL query")
        sections.append("")
    else:
        sections.append("=" * 60)
        sections.append("TASK")
        sections.append("=" * 60)
        sections.append("")

    # --- Phần 4: User Question ---
    sections.append(f"Question: {user_question}")
    sections.append("")
    sections.append("SQL:")

    prompt = "\n".join(sections)

    logger.debug(
        "Prompt built: %d chars, %d examples, decomposition=%s",
        len(prompt),
        len(selected_examples),
        include_decomposition,
    )

    return prompt


def build_correction_prompt(
    user_question: str,
    schema_text: str,
    failed_sql: str,
    error_message: str,
) -> str:
    """Xây dựng prompt cho Self-Correction Loop.

    Khi SQL bị lỗi, gửi lại cho LLM kèm thông tin lỗi để sửa.
    Dựa trên kỹ thuật Self-Correction từ DIN-SQL.

    Args:
        user_question: Câu hỏi gốc.
        schema_text: Mô tả schema.
        failed_sql: Câu SQL đã thất bại.
        error_message: Thông báo lỗi từ DuckDB.

    Returns:
        Prompt yêu cầu LLM sửa SQL.
    """
    sections: list[str] = [
        "=" * 60,
        "SQL CORRECTION TASK",
        "=" * 60,
        "",
        "The following SQL query generated for a user question has an error.",
        "Please fix the SQL query based on the error message and schema.",
        "",
        "-" * 40,
        "DATABASE SCHEMA:",
        "-" * 40,
        schema_text,
        "",
        "-" * 40,
        "ORIGINAL QUESTION:",
        "-" * 40,
        user_question,
        "",
        "-" * 40,
        "FAILED SQL:",
        "-" * 40,
        failed_sql,
        "",
        "-" * 40,
        "ERROR MESSAGE:",
        "-" * 40,
        error_message,
        "",
        "-" * 40,
        "INSTRUCTIONS:",
        "-" * 40,
        "1. Analyze the error message carefully.",
        "2. Check column names and table names against the schema.",
        "3. Fix the SQL query to resolve the error.",
        "4. Return ONLY the corrected SQL query, no explanations.",
        "",
        "CORRECTED SQL:",
    ]

    return "\n".join(sections)


def build_insight_prompt(
    user_question: str,
    sql_query: str,
    query_result_preview: str,
    row_count: int,
) -> str:
    """Xây dựng prompt để sinh nhận xét insight từ kết quả query.

    Sẽ được sử dụng đầy đủ ở Tuần 4, nhưng chuẩn bị sẵn ở đây.

    Args:
        user_question: Câu hỏi gốc.
        sql_query: SQL đã chạy.
        query_result_preview: Vài dòng đầu của kết quả (dạng text/markdown).
        row_count: Tổng số dòng kết quả.

    Returns:
        Prompt cho Insight Generation.
    """
    sections: list[str] = [
        "You are a data analyst. Based on the query results below, write a brief",
        "insight summary in Vietnamese (2-3 sentences). Focus on key trends,",
        "notable patterns, and actionable observations.",
        "",
        f"User Question: {user_question}",
        f"SQL Query: {sql_query}",
        f"Total rows: {row_count}",
        "",
        "Query Results (preview):",
        query_result_preview,
        "",
        "Write your insight in Vietnamese:",
    ]

    return "\n".join(sections)


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def _select_examples(num_examples: int) -> list[dict[str, str]]:
    """Chọn ví dụ few-shot cân bằng độ khó.

    Ưu tiên lấy đều từ easy, medium, hard.

    Args:
        num_examples: Số ví dụ cần chọn.

    Returns:
        Danh sách examples đã chọn.
    """
    if num_examples >= len(FEW_SHOT_EXAMPLES):
        return FEW_SHOT_EXAMPLES.copy()

    # Phân nhóm theo độ khó
    easy = [e for e in FEW_SHOT_EXAMPLES if e["difficulty"] == "easy"]
    medium = [e for e in FEW_SHOT_EXAMPLES if e["difficulty"] == "medium"]
    hard = [e for e in FEW_SHOT_EXAMPLES if e["difficulty"] == "hard"]

    selected: list[dict[str, str]] = []
    groups = [easy, medium, hard]

    # Round-robin chọn từ các nhóm
    idx = 0
    while len(selected) < num_examples:
        group = groups[idx % len(groups)]
        group_offset = len([s for s in selected if s["difficulty"] == group[0]["difficulty"]]) if group else 0
        if group_offset < len(group):
            selected.append(group[group_offset])
        idx += 1
        # An toàn: tránh vòng lặp vô hạn
        if idx > num_examples * 3:
            break

    return selected[:num_examples]


def get_system_instruction() -> str:
    """Trả về system instruction cho Gemini.

    Returns:
        System instruction string.
    """
    return SYSTEM_INSTRUCTION


def get_few_shot_examples() -> list[dict[str, str]]:
    """Trả về danh sách tất cả few-shot examples.

    Returns:
        List các dict chứa question, sql, difficulty.
    """
    return FEW_SHOT_EXAMPLES.copy()


if __name__ == "__main__":
    # Demo: In prompt mẫu
    from src.data.schema_metadata import format_schema_for_prompt

    schema = format_schema_for_prompt()
    question = "Top 5 danh muc san pham co doanh thu cao nhat nam 2018?"

    prompt = build_text_to_sql_prompt(
        user_question=question,
        schema_text=schema,
        num_examples=5,
    )

    print("PROMPT LENGTH:", len(prompt), "chars")
    print("=" * 60)
    print(prompt[:2000])
    print("...")
    print(prompt[-500:])
