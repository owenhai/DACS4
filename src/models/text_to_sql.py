"""Pipeline Text-to-SQL: Chuyển đổi câu hỏi tự nhiên thành truy vấn SQL.

Luồng xử lý chính:
    Câu hỏi (Tiếng Việt/Anh)
    -> Schema Linking + Few-shot Prompt
    -> Gemini Flash sinh SQL
    -> Trích xuất SQL từ response
    -> Thực thi trên DuckDB
    -> Trả về DataFrame kết quả

Module này tích hợp:
- GeminiClient (llm_client.py) để gọi LLM
- Prompt Templates (prompt_templates.py) để xây dựng prompt
- Schema Metadata (schema_metadata.py) để cung cấp context
- DuckDB để thực thi SQL

Cơ chế Self-Correction cơ bản đã có sẵn, sẽ được nâng cấp
thêm SQL Guardrails ở Tuần 3.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.data.schema_metadata import format_schema_for_prompt
from src.models.llm_client import GeminiClient
from src.models.prompt_templates import (
    build_correction_prompt,
    build_text_to_sql_prompt,
    get_system_instruction,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ===========================================================================
# Data Classes
# ===========================================================================

@dataclass
class QueryResult:
    """Kết quả của một truy vấn Text-to-SQL.

    Attributes:
        question: Câu hỏi gốc của người dùng.
        generated_sql: Câu SQL được sinh bởi LLM.
        dataframe: DataFrame kết quả (None nếu lỗi).
        success: Truy vấn có thành công không.
        error_message: Thông báo lỗi (nếu có).
        execution_time_ms: Thời gian thực thi (milliseconds).
        correction_attempts: Số lần sửa lỗi đã thử.
        correction_history: Lịch sử các lần sửa SQL.
    """

    question: str
    generated_sql: str
    dataframe: pd.DataFrame | None = None
    success: bool = False
    error_message: str | None = None
    execution_time_ms: float = 0.0
    correction_attempts: int = 0
    correction_history: list[dict[str, str]] = field(default_factory=list)


# ===========================================================================
# Text-to-SQL Pipeline
# ===========================================================================

class TextToSQLPipeline:
    """Pipeline chuyển đổi câu hỏi tự nhiên thành SQL và thực thi.

    Luồng xử lý:
    1. Nhận câu hỏi từ người dùng
    2. Xây dựng prompt với Schema Linking + Few-shot
    3. Gọi Gemini Flash sinh SQL
    4. Trích xuất SQL từ response
    5. Thực thi SQL trên DuckDB
    6. Nếu lỗi -> Self-Correction Loop (retry với error context)
    7. Trả về QueryResult

    Attributes:
        llm_client: GeminiClient instance.
        db_path: Đường dẫn file DuckDB.
        schema_text: Schema metadata đã format cho prompt.
        max_corrections: Số lần sửa lỗi tối đa.
        num_few_shot: Số ví dụ few-shot trong prompt.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        llm_client: GeminiClient | None = None,
        max_corrections: int = 3,
        num_few_shot: int = 5,
    ) -> None:
        """Khởi tạo Text-to-SQL Pipeline.

        Args:
            db_path: Đường dẫn file DuckDB.
                Mặc định: data/database/olist_analytics.duckdb
            llm_client: GeminiClient đã khởi tạo.
                Nếu None, tạo mới với cấu hình mặc định.
            max_corrections: Số lần self-correction tối đa.
            num_few_shot: Số ví dụ few-shot trong prompt.
        """
        # Database path
        if db_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            db_path = project_root / "data" / "database" / "olist_analytics.duckdb"
        self.db_path = Path(db_path)

        # Kiểm tra DB tồn tại
        if not self.db_path.exists():
            # Thử path khác (data/olist.duckdb)
            alt_path = self.db_path.parent.parent / "olist.duckdb"
            if alt_path.exists():
                self.db_path = alt_path
                logger.info("Su dung database tai: %s", self.db_path)
            else:
                raise FileNotFoundError(
                    f"Khong tim thay database: {self.db_path}"
                )

        # LLM Client
        if llm_client is None:
            self.llm_client = GeminiClient()
        else:
            self.llm_client = llm_client

        # Config
        self.max_corrections = max_corrections
        self.num_few_shot = num_few_shot

        # Load schema text (chỉ load 1 lần)
        self.schema_text = format_schema_for_prompt()

        # System instruction
        self.system_instruction = get_system_instruction()

        logger.info(
            "TextToSQLPipeline initialized: db=%s, max_corrections=%d",
            self.db_path.name,
            self.max_corrections,
        )

    def ask(self, question: str) -> QueryResult:
        """Xử lý câu hỏi: sinh SQL, thực thi, và trả về kết quả.

        Đây là method chính của pipeline.

        Args:
            question: Câu hỏi bằng ngôn ngữ tự nhiên (Tiếng Việt hoặc Anh).

        Returns:
            QueryResult chứa SQL, DataFrame kết quả, và metadata.
        """
        start_time = time.time()
        logger.info("Processing question: %s", question[:100])

        # Bước 1: Sinh SQL từ LLM
        try:
            generated_sql = self._generate_sql(question)
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error("LLM generation failed: %s", str(e))
            return QueryResult(
                question=question,
                generated_sql="",
                success=False,
                error_message=f"Loi sinh SQL: {str(e)}",
                execution_time_ms=elapsed,
            )

        # Bước 2: Thực thi SQL trên DuckDB (với Self-Correction Loop)
        result = self._execute_with_correction(question, generated_sql)
        result.execution_time_ms = (time.time() - start_time) * 1000

        logger.info(
            "Query completed: success=%s, time=%.0fms, corrections=%d",
            result.success,
            result.execution_time_ms,
            result.correction_attempts,
        )

        return result

    def _generate_sql(self, question: str) -> str:
        """Sinh SQL từ câu hỏi sử dụng LLM.

        Args:
            question: Câu hỏi của người dùng.

        Returns:
            Câu SQL đã được trích xuất và làm sạch.
        """
        # Xây dựng prompt
        prompt = build_text_to_sql_prompt(
            user_question=question,
            schema_text=self.schema_text,
            num_examples=self.num_few_shot,
            include_decomposition=True,
        )

        # Gọi LLM
        raw_response = self.llm_client.generate(
            prompt=prompt,
            system_instruction=self.system_instruction,
        )

        # Trích xuất SQL từ response
        sql = self._extract_sql(raw_response)

        logger.info("Generated SQL: %s", sql[:200])
        return sql

    def _execute_with_correction(
        self, question: str, sql: str
    ) -> QueryResult:
        """Thực thi SQL với cơ chế Self-Correction Loop.

        Nếu SQL thất bại, gửi lại cho LLM kèm lỗi để sửa.
        Lặp tối đa max_corrections lần.

        Args:
            question: Câu hỏi gốc.
            sql: SQL đã sinh.

        Returns:
            QueryResult với kết quả cuối cùng.
        """
        current_sql = sql
        correction_history: list[dict[str, str]] = []

        for attempt in range(self.max_corrections + 1):
            # Thử thực thi SQL
            df, error = self._execute_sql(current_sql)

            if df is not None:
                # Thành công!
                return QueryResult(
                    question=question,
                    generated_sql=current_sql,
                    dataframe=df,
                    success=True,
                    correction_attempts=attempt,
                    correction_history=correction_history,
                )

            # Thất bại - ghi nhận lịch sử
            correction_history.append({
                "attempt": str(attempt),
                "sql": current_sql,
                "error": error or "Unknown error",
            })

            logger.warning(
                "SQL execution failed (attempt %d/%d): %s",
                attempt + 1,
                self.max_corrections + 1,
                error,
            )

            # Nếu đã hết lượt retry
            if attempt >= self.max_corrections:
                break

            # Self-Correction: Gọi LLM sửa SQL
            try:
                current_sql = self._correct_sql(
                    question, current_sql, error or "Unknown error"
                )
                logger.info(
                    "Self-correction attempt %d: new SQL generated",
                    attempt + 1,
                )
            except Exception as e:
                logger.error("Self-correction failed: %s", str(e))
                break

        # Tất cả attempts thất bại
        return QueryResult(
            question=question,
            generated_sql=current_sql,
            success=False,
            error_message=error,
            correction_attempts=len(correction_history),
            correction_history=correction_history,
        )

    def _correct_sql(
        self, question: str, failed_sql: str, error_message: str
    ) -> str:
        """Gọi LLM để sửa SQL bị lỗi.

        Args:
            question: Câu hỏi gốc.
            failed_sql: SQL đã thất bại.
            error_message: Lỗi từ DuckDB.

        Returns:
            SQL đã sửa.
        """
        correction_prompt = build_correction_prompt(
            user_question=question,
            schema_text=self.schema_text,
            failed_sql=failed_sql,
            error_message=error_message,
        )

        raw_response = self.llm_client.generate(
            prompt=correction_prompt,
            system_instruction=self.system_instruction,
        )

        return self._extract_sql(raw_response)

    def _execute_sql(self, sql: str) -> tuple[pd.DataFrame | None, str | None]:
        """Thực thi SQL trên DuckDB và trả về kết quả.

        Args:
            sql: Câu SQL cần thực thi.

        Returns:
            Tuple (DataFrame, None) nếu thành công,
            hoặc (None, error_message) nếu thất bại.
        """
        try:
            conn = duckdb.connect(str(self.db_path), read_only=True)
            try:
                df = conn.execute(sql).fetchdf()
                return df, None
            finally:
                conn.close()
        except duckdb.Error as e:
            return None, f"DuckDB Error: {str(e)}"
        except Exception as e:
            return None, f"Execution Error: {str(e)}"

    @staticmethod
    def _extract_sql(llm_response: str) -> str:
        """Trích xuất câu SQL từ phản hồi của LLM.

        Xử lý các trường hợp:
        - SQL nằm trong code block ```sql ... ```
        - SQL thuần (không có markdown)
        - SQL có lẫn text giải thích

        Args:
            llm_response: Phản hồi thô từ LLM.

        Returns:
            Câu SQL đã được làm sạch.
        """
        text = llm_response.strip()

        # Trường hợp 1: SQL trong code block ```sql ... ```
        code_block_pattern = r"```(?:sql)?\s*\n?(.*?)\n?```"
        matches = re.findall(code_block_pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            # Lấy code block cuối cùng (thường là kết quả cuối)
            sql = matches[-1].strip()
            if sql:
                return sql

        # Trường hợp 2: Tìm SELECT statement
        select_pattern = r"((?:WITH|SELECT)\b.*?;)"
        matches = re.findall(select_pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[-1].strip()

        # Trường hợp 3: Tìm SELECT không có dấu chấm phẩy
        select_no_semi = r"((?:WITH|SELECT)\b.*)"
        matches = re.findall(select_no_semi, text, re.DOTALL | re.IGNORECASE)
        if matches:
            sql = matches[-1].strip()
            # Loại bỏ text thừa sau SQL (nếu có dòng trống ngăn cách)
            lines = sql.split("\n")
            clean_lines: list[str] = []
            for line in lines:
                stripped = line.strip()
                # Dừng khi gặp text giải thích (không phải SQL)
                if stripped and not stripped.startswith("--") and not any(
                    kw in stripped.upper()
                    for kw in [
                        "SELECT", "FROM", "WHERE", "JOIN", "GROUP",
                        "ORDER", "HAVING", "LIMIT", "WITH", "AS",
                        "ON", "AND", "OR", "IN", "NOT", "NULL",
                        "CASE", "WHEN", "THEN", "ELSE", "END",
                        "COUNT", "SUM", "AVG", "MIN", "MAX",
                        "ROUND", "COALESCE", "DISTINCT", "CROSS",
                        "LEFT", "RIGHT", "INNER", "OUTER", "FULL",
                        "UNION", "EXCEPT", "INTERSECT", "EXISTS",
                        "BETWEEN", "LIKE", "IS", "DESC", "ASC",
                        "(", ")", ",", "=", ">", "<", "'", "*",
                    ]
                ):
                    break
                clean_lines.append(line)
            if clean_lines:
                return "\n".join(clean_lines).strip()

        # Fallback: trả về toàn bộ (loại bỏ markdown)
        text = re.sub(r"```\w*\n?", "", text)
        text = re.sub(r"```", "", text)
        return text.strip()

    def test_connection(self) -> bool:
        """Kiểm tra kết nối DuckDB.

        Returns:
            True nếu kết nối thành công.
        """
        try:
            conn = duckdb.connect(str(self.db_path), read_only=True)
            tables = conn.execute("SHOW TABLES").fetchall()
            conn.close()
            logger.info("DB connection OK: %d tables", len(tables))
            return True
        except Exception as e:
            logger.error("DB connection failed: %s", str(e))
            return False


# ===========================================================================
# Convenience Function
# ===========================================================================

def create_pipeline(
    db_path: str | Path | None = None,
    api_key: str | None = None,
) -> TextToSQLPipeline:
    """Tạo pipeline Text-to-SQL với cấu hình mặc định.

    Hàm tiện ích để khởi tạo nhanh pipeline.

    Args:
        db_path: Đường dẫn DuckDB (None = mặc định).
        api_key: Google API key (None = đọc từ .env).

    Returns:
        TextToSQLPipeline đã sẵn sàng sử dụng.
    """
    client = GeminiClient(api_key=api_key) if api_key else None
    return TextToSQLPipeline(
        db_path=db_path,
        llm_client=client,
    )


# ===========================================================================
# Main - Demo & Test
# ===========================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("TEXT-TO-SQL PIPELINE - DEMO")
    print("=" * 60)

    # Khoi tao pipeline
    try:
        pipeline = TextToSQLPipeline()
    except (ValueError, FileNotFoundError) as e:
        print(f"\nSetup error: {e}")
        sys.exit(1)

    # Kiem tra ket noi DB
    if not pipeline.test_connection():
        print("Cannot connect to database!")
        sys.exit(1)

    # Demo cau hoi
    demo_questions = [
        "Tong so don hang la bao nhieu?",
        "Top 5 danh muc san pham co doanh thu cao nhat?",
        "Doanh thu theo tung bang cua khach hang, sap xep giam dan?",
    ]

    for q in demo_questions:
        print(f"\n{'─' * 60}")
        print(f"Question: {q}")
        print("─" * 60)

        result = pipeline.ask(q)

        print(f"Success: {result.success}")
        print(f"SQL:\n{result.generated_sql}")
        print(f"Time: {result.execution_time_ms:.0f}ms")
        print(f"Corrections: {result.correction_attempts}")

        if result.success and result.dataframe is not None:
            print(f"Rows: {len(result.dataframe)}")
            print(result.dataframe.head(10).to_string())
        elif result.error_message:
            print(f"Error: {result.error_message}")
