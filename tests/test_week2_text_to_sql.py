"""Tests cho Week 2 - Text-to-SQL Pipeline.

Kiểm tra:
1. Prompt template được xây dựng đúng
2. SQL extraction từ LLM response
3. Pipeline integration (cần API key)
"""

import unittest
from src.models.prompt_templates import (
    build_text_to_sql_prompt,
    build_correction_prompt,
    get_system_instruction,
    get_few_shot_examples,
    FEW_SHOT_EXAMPLES,
    _select_examples,
)
from src.models.text_to_sql import TextToSQLPipeline
from src.data.schema_metadata import format_schema_for_prompt


class TestPromptTemplates(unittest.TestCase):
    """Test module prompt_templates.py."""

    def setUp(self):
        """Chuẩn bị schema text cho các test."""
        self.schema_text = format_schema_for_prompt()

    def test_system_instruction_exists(self):
        """System instruction không rỗng và chứa các quy tắc quan trọng."""
        instruction = get_system_instruction()
        self.assertIsInstance(instruction, str)
        self.assertGreater(len(instruction), 100)
        # Phải có quy tắc SELECT only
        self.assertIn("SELECT", instruction)

    def test_few_shot_examples_count(self):
        """Phải có đủ ví dụ few-shot cho 3 mức độ khó."""
        examples = get_few_shot_examples()
        self.assertGreaterEqual(len(examples), 6)

        difficulties = {e["difficulty"] for e in examples}
        self.assertIn("easy", difficulties)
        self.assertIn("medium", difficulties)
        self.assertIn("hard", difficulties)

    def test_few_shot_examples_structure(self):
        """Mỗi ví dụ phải có question, sql, difficulty."""
        for ex in FEW_SHOT_EXAMPLES:
            self.assertIn("question", ex)
            self.assertIn("sql", ex)
            self.assertIn("difficulty", ex)
            self.assertIsInstance(ex["question"], str)
            self.assertIsInstance(ex["sql"], str)
            self.assertIn(ex["difficulty"], ["easy", "medium", "hard"])

    def test_build_prompt_contains_schema(self):
        """Prompt phải chứa schema text."""
        prompt = build_text_to_sql_prompt(
            user_question="Test question?",
            schema_text=self.schema_text,
        )
        self.assertIn("fact_orders", prompt)
        self.assertIn("dim_customers", prompt)
        self.assertIn("Test question?", prompt)

    def test_build_prompt_contains_examples(self):
        """Prompt phải chứa ví dụ few-shot."""
        prompt = build_text_to_sql_prompt(
            user_question="Test?",
            schema_text=self.schema_text,
            num_examples=3,
        )
        self.assertIn("Example 1", prompt)
        self.assertIn("Example 2", prompt)
        self.assertIn("Example 3", prompt)

    def test_build_correction_prompt(self):
        """Correction prompt phải chứa SQL lỗi và error message."""
        prompt = build_correction_prompt(
            user_question="Test?",
            schema_text=self.schema_text,
            failed_sql="SELECT * FROM nonexistent_table;",
            error_message="Table 'nonexistent_table' does not exist",
        )
        self.assertIn("nonexistent_table", prompt)
        self.assertIn("does not exist", prompt)
        self.assertIn("CORRECTED SQL", prompt)

    def test_select_examples_balanced(self):
        """Hàm chọn ví dụ phải cân bằng độ khó."""
        selected = _select_examples(3)
        self.assertEqual(len(selected), 3)
        difficulties = [e["difficulty"] for e in selected]
        # Phải có ít nhất 1 từ mỗi nhóm
        self.assertIn("easy", difficulties)
        self.assertIn("medium", difficulties)
        self.assertIn("hard", difficulties)

    def test_select_examples_max(self):
        """Khi yêu cầu nhiều hơn có, trả về tất cả."""
        selected = _select_examples(100)
        self.assertEqual(len(selected), len(FEW_SHOT_EXAMPLES))


class TestSQLExtraction(unittest.TestCase):
    """Test trích xuất SQL từ LLM response."""

    def test_extract_from_code_block(self):
        """Trích xuất SQL từ markdown code block."""
        response = """Here's the query:

```sql
SELECT COUNT(DISTINCT order_id) AS total_orders
FROM fact_orders;
```

This will give you the total number of orders."""

        sql = TextToSQLPipeline._extract_sql(response)
        self.assertIn("SELECT", sql)
        self.assertIn("fact_orders", sql)
        self.assertNotIn("```", sql)
        self.assertNotIn("Here's", sql)

    def test_extract_plain_sql(self):
        """Trích xuất SQL thuần (không có code block)."""
        response = "SELECT SUM(price) AS total_revenue FROM fact_orders;"
        sql = TextToSQLPipeline._extract_sql(response)
        self.assertEqual(sql, response)

    def test_extract_sql_with_cte(self):
        """Trích xuất SQL có CTE (WITH clause)."""
        response = """```sql
WITH monthly AS (
    SELECT d.month, SUM(f.price) AS revenue
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.month
)
SELECT * FROM monthly ORDER BY month;
```"""
        sql = TextToSQLPipeline._extract_sql(response)
        self.assertIn("WITH", sql)
        self.assertIn("monthly", sql)

    def test_extract_sql_no_semicolon(self):
        """Trích xuất SQL không có dấu chấm phẩy."""
        response = "SELECT COUNT(*) FROM fact_orders"
        sql = TextToSQLPipeline._extract_sql(response)
        self.assertIn("SELECT", sql)

    def test_extract_multiple_code_blocks(self):
        """Khi có nhiều code blocks, lấy cái cuối cùng."""
        response = """First attempt:
```sql
SELECT * FROM wrong_table;
```

Corrected:
```sql
SELECT * FROM fact_orders LIMIT 10;
```"""
        sql = TextToSQLPipeline._extract_sql(response)
        self.assertIn("fact_orders", sql)


class TestPipelineInit(unittest.TestCase):
    """Test khởi tạo pipeline (không cần API key)."""

    def test_schema_text_loaded(self):
        """Schema text phải chứa thông tin bảng."""
        schema = format_schema_for_prompt()
        self.assertIn("fact_orders", schema)
        self.assertIn("dim_customers", schema)
        self.assertIn("dim_products", schema)
        self.assertIn("dim_sellers", schema)
        self.assertIn("dim_date", schema)
        self.assertIn("customer_key", schema)

    def test_schema_contains_business_context(self):
        """Schema phải có business context."""
        schema = format_schema_for_prompt()
        self.assertIn("Brazilian", schema)
        self.assertIn("BRL", schema)

    def test_schema_contains_join_patterns(self):
        """Schema phải có ví dụ JOIN."""
        schema = format_schema_for_prompt()
        self.assertIn("JOIN", schema)
        self.assertIn("GROUP BY", schema)


if __name__ == "__main__":
    unittest.main(verbosity=2)
