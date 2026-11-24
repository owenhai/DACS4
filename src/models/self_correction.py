"""Self-Correction Loop: tự sửa SQL lỗi bằng cách gửi phản hồi lỗi cho LLM.

Luồng xử lý::

    SQL -> Guardrails -> Thực thi (có timeout) -> OK -> trả kết quả
                |                  |
                |                  +-> Lỗi DuckDB -> phân loại lỗi -> prompt sửa -> LLM -> SQL mới
                +-> Lỗi có thể sửa (bảng/cột sai, quá phức tạp) -> prompt sửa -> LLM -> SQL mới
                +-> Vi phạm bảo mật -> DỪNG NGAY (không gửi cho LLM)

Lặp tối đa ``max_retries`` lần sửa.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import duckdb
import pandas as pd

from src.models.prompt_templates import build_correction_prompt
from src.models.sql_guardrails import SQLGuardrails, ValidationResult

logger = logging.getLogger(__name__)


# ===========================================================================
# Phân loại lỗi
# ===========================================================================

ERR_SYNTAX = "syntax"
ERR_UNKNOWN_TABLE = "unknown_table"
ERR_UNKNOWN_COLUMN = "unknown_column"
ERR_TYPE_MISMATCH = "type_mismatch"
ERR_TIMEOUT = "timeout"
ERR_EMPTY_RESULT = "empty_result"
ERR_SECURITY = "security"
ERR_COMPLEXITY = "complexity"
ERR_LLM = "llm_error"
ERR_OTHER = "other"

#: Gợi ý sửa lỗi gửi kèm cho LLM theo từng loại lỗi.
CORRECTION_HINTS: dict[str, str] = {
    ERR_SYNTAX: "Lỗi cú pháp SQL. Kiểm tra dấu ngoặc, dấu phẩy, từ khóa và cú pháp DuckDB.",
    ERR_UNKNOWN_TABLE: "Bảng không tồn tại. Chỉ dùng các bảng có trong schema.",
    ERR_UNKNOWN_COLUMN: (
        "Cột không tồn tại hoặc sai bảng. Kiểm tra lại tên cột trong schema "
        "và alias của bảng. Cột tính toán trong SELECT không dùng được trong WHERE."
    ),
    ERR_TYPE_MISMATCH: (
        "Kiểu dữ liệu không tương thích. Dùng CAST(... AS ...) hoặc so sánh "
        "đúng kiểu (ví dụ: date_key là INTEGER dạng YYYYMMDD)."
    ),
    ERR_TIMEOUT: (
        "Truy vấn chạy quá lâu. Hãy đơn giản hóa: giảm JOIN, lọc sớm bằng WHERE, "
        "tránh subquery tương quan, dùng CTE."
    ),
    ERR_EMPTY_RESULT: (
        "Truy vấn không trả về dòng nào. Kiểm tra điều kiện lọc (giá trị chuỗi, "
        "chữ hoa/thường, khoảng thời gian dữ liệu 2016-2018)."
    ),
    ERR_COMPLEXITY: "Truy vấn quá phức tạp. Hãy dùng CTE và giảm số JOIN/subquery.",
}


def classify_error(error_message: str) -> str:
    """Phân loại thông báo lỗi DuckDB thành loại lỗi chuẩn.

    Args:
        error_message: Chuỗi lỗi từ DuckDB / guardrails.

    Returns:
        Một trong các hằng ``ERR_*``.
    """
    msg = (error_message or "").lower()
    if "interrupt" in msg or "timeout" in msg or "timed out" in msg:
        return ERR_TIMEOUT
    if "parser error" in msg or "syntax error" in msg:
        return ERR_SYNTAX
    if ("catalog error" in msg and "table" in msg) or "table with name" in msg:
        return ERR_UNKNOWN_TABLE
    if (
        ("referenced column" in msg)
        or ("column" in msg and "not found" in msg)
        or ("binder error" in msg and "column" in msg and "does not" in msg)
        or ("must appear in the group by" in msg)
    ):
        return ERR_UNKNOWN_COLUMN
    if (
        "conversion error" in msg
        or "no function matches" in msg
        or "cannot compare" in msg
        or "could not convert" in msg
        or "type mismatch" in msg
        or "implicit cast" in msg
    ):
        return ERR_TYPE_MISMATCH
    if "catalog error" in msg:
        return ERR_UNKNOWN_TABLE
    if "binder error" in msg:
        return ERR_UNKNOWN_COLUMN
    return ERR_OTHER


# ===========================================================================
# Data classes
# ===========================================================================

@dataclass
class ExecutionResult:
    """Kết quả một lần thực thi SQL."""

    sql: str
    success: bool
    dataframe: pd.DataFrame | None = None
    error_message: str | None = None
    error_type: str | None = None
    execution_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)


@dataclass
class CorrectionOutcome:
    """Kết quả cuối cùng của Self-Correction Loop."""

    question: str
    final_sql: str
    success: bool
    dataframe: pd.DataFrame | None = None
    error_message: str | None = None
    error_type: str | None = None
    attempts: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def corrections(self) -> int:
        """Số lần LLM đã được yêu cầu sửa SQL."""
        return max(0, self.attempts - 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "final_sql": self.final_sql,
            "success": self.success,
            "row_count": None if self.dataframe is None else len(self.dataframe),
            "error_message": self.error_message,
            "error_type": self.error_type,
            "attempts": self.attempts,
            "corrections": self.corrections,
            "history": self.history,
            "warnings": self.warnings,
        }


@dataclass
class CorrectionMetrics:
    """Thống kê hiệu quả Self-Correction (dùng cho đánh giá Tuần 6)."""

    total_queries: int = 0
    first_try_success: int = 0
    corrected_success: int = 0
    failed: int = 0
    blocked_security: int = 0
    total_corrections: int = 0
    error_counts: Counter = field(default_factory=Counter)
    fixed_error_counts: Counter = field(default_factory=Counter)

    def record(self, outcome: CorrectionOutcome) -> None:
        self.total_queries += 1
        self.total_corrections += outcome.corrections
        for h in outcome.history:
            if h.get("error_type"):
                self.error_counts[h["error_type"]] += 1
        if outcome.error_type == ERR_SECURITY:
            self.blocked_security += 1
        if outcome.success and outcome.corrections == 0:
            self.first_try_success += 1
        elif outcome.success:
            self.corrected_success += 1
            for h in outcome.history:
                if h.get("error_type"):
                    self.fixed_error_counts[h["error_type"]] += 1
        else:
            self.failed += 1

    @property
    def avg_corrections(self) -> float:
        return self.total_corrections / self.total_queries if self.total_queries else 0.0

    @property
    def correction_success_rate(self) -> float:
        """Tỉ lệ sửa thành công trên các truy vấn bị lỗi ở lần đầu (không tính bị chặn bảo mật)."""
        needed = self.corrected_success + self.failed - self.blocked_security
        return self.corrected_success / needed if needed > 0 else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "first_try_success": self.first_try_success,
            "corrected_success": self.corrected_success,
            "failed": self.failed,
            "blocked_security": self.blocked_security,
            "avg_corrections": round(self.avg_corrections, 3),
            "correction_success_rate": round(self.correction_success_rate, 3),
            "error_counts": dict(self.error_counts),
            "fixed_error_counts": dict(self.fixed_error_counts),
        }


# ===========================================================================
# Self-Correction Loop
# ===========================================================================

class SelfCorrectionLoop:
    """Vòng lặp validate -> execute -> correct.

    Args:
        db_path: Đường dẫn DuckDB.
        sql_generator: Hàm ``prompt -> SQL`` (đã trích xuất), dùng để sinh lại SQL.
        schema_text: Schema đã format, nhúng vào prompt sửa lỗi.
        guardrails: Bộ kiểm duyệt SQL.
        max_retries: Số lần sửa tối đa.
        timeout_seconds: Thời gian tối đa cho một truy vấn DuckDB.
        retry_on_empty: Có yêu cầu LLM sửa khi kết quả rỗng không.
    """

    def __init__(
        self,
        db_path: str | Path,
        sql_generator: Callable[[str], str],
        schema_text: str,
        guardrails: SQLGuardrails | None = None,
        max_retries: int = 3,
        timeout_seconds: float = 30.0,
        retry_on_empty: bool = False,
    ) -> None:
        self.db_path = Path(db_path)
        self.sql_generator = sql_generator
        self.schema_text = schema_text
        self.guardrails = guardrails or SQLGuardrails()
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.retry_on_empty = retry_on_empty
        self.metrics = CorrectionMetrics()

    # ------------------------------------------------------------------

    def attempt_execution(self, sql: str) -> ExecutionResult:
        """Kiểm duyệt rồi thực thi SQL, bắt mọi lỗi.

        Returns:
            ExecutionResult; nếu bị guardrails chặn thì không thực thi.
        """
        validation: ValidationResult = self.guardrails.validate_sql(sql)
        if not validation.is_valid:
            return ExecutionResult(
                sql=sql,
                success=False,
                error_message=f"Guardrails: {validation.error_message}",
                error_type=validation.error_type or ERR_OTHER,
            )

        safe_sql = validation.sanitized_sql
        start = time.perf_counter()
        df, error = self._execute_with_timeout(safe_sql)
        elapsed = (time.perf_counter() - start) * 1000

        if error is not None:
            return ExecutionResult(
                sql=safe_sql,
                success=False,
                error_message=error,
                error_type=classify_error(error),
                execution_time_ms=elapsed,
                warnings=validation.warnings,
            )

        warnings = list(validation.warnings)
        if df is not None and df.empty:
            warnings.append("Truy vấn trả về 0 dòng.")
        return ExecutionResult(
            sql=safe_sql,
            success=True,
            dataframe=df,
            execution_time_ms=elapsed,
            warnings=warnings,
        )

    def build_correction_prompt(
        self,
        original_question: str,
        failed_sql: str,
        error_msg: str,
        error_type: str | None = None,
    ) -> str:
        """Tạo prompt yêu cầu LLM sửa SQL, kèm gợi ý theo loại lỗi."""
        hint = CORRECTION_HINTS.get(error_type or "", "")
        full_error = f"{error_msg}\nLoại lỗi: {error_type or ERR_OTHER}."
        if hint:
            full_error += f"\nGợi ý: {hint}"
        return build_correction_prompt(
            user_question=original_question,
            schema_text=self.schema_text,
            failed_sql=failed_sql,
            error_message=full_error,
        )

    def run_with_correction(
        self,
        question: str,
        initial_sql: str,
        max_retries: int | None = None,
    ) -> CorrectionOutcome:
        """Vòng lặp chính: thực thi, nếu lỗi thì nhờ LLM sửa (tối đa ``max_retries``).

        Args:
            question: Câu hỏi gốc của người dùng.
            initial_sql: SQL sinh ở lần đầu.
            max_retries: Ghi đè số lần sửa tối đa.

        Returns:
            CorrectionOutcome (có ``to_dict()``).
        """
        retries = self.max_retries if max_retries is None else max_retries
        current_sql = initial_sql
        history: list[dict[str, Any]] = []
        last: ExecutionResult | None = None

        for attempt in range(retries + 1):
            last = self.attempt_execution(current_sql)
            history.append({
                "attempt": attempt + 1,
                "sql": current_sql,
                "success": last.success,
                "error_type": last.error_type,
                "error": last.error_message,
                "execution_time_ms": round(last.execution_time_ms, 1),
            })

            needs_retry_empty = (
                last.success
                and self.retry_on_empty
                and last.dataframe is not None
                and last.dataframe.empty
                and attempt < retries
            )
            if last.success and not needs_retry_empty:
                logger.info("SQL thành công ở lần thử %d", attempt + 1)
                return self._finish(CorrectionOutcome(
                    question=question,
                    final_sql=last.sql,
                    success=True,
                    dataframe=last.dataframe,
                    attempts=attempt + 1,
                    history=history,
                    warnings=last.warnings,
                ))

            error_type = ERR_EMPTY_RESULT if needs_retry_empty else last.error_type
            error_msg = (
                "Truy vấn chạy thành công nhưng trả về 0 dòng."
                if needs_retry_empty else (last.error_message or "Unknown error")
            )
            if needs_retry_empty:
                history[-1]["error_type"] = ERR_EMPTY_RESULT

            logger.warning(
                "Lần thử %d/%d thất bại [%s]: %s",
                attempt + 1, retries + 1, error_type, error_msg,
            )

            # Vi phạm bảo mật -> dừng ngay, không nhờ LLM "lách" luật
            if error_type == ERR_SECURITY:
                logger.warning("Dừng Self-Correction do vi phạm bảo mật.")
                break
            if attempt >= retries:
                break

            prompt = self.build_correction_prompt(
                question, current_sql, error_msg, error_type
            )
            try:
                current_sql = self.sql_generator(prompt)
            except Exception as e:  # LLM lỗi -> không thể sửa tiếp
                logger.error("LLM không sinh được SQL sửa: %s", e)
                history.append({
                    "attempt": attempt + 2,
                    "sql": "",
                    "success": False,
                    "error_type": ERR_LLM,
                    "error": str(e),
                    "execution_time_ms": 0.0,
                })
                break

        assert last is not None
        final_type = history[-1]["error_type"] or last.error_type
        return self._finish(CorrectionOutcome(
            question=question,
            final_sql=last.sql,
            success=False,
            error_message=history[-1]["error"] or last.error_message,
            error_type=final_type,
            attempts=sum(1 for h in history if h["error_type"] != ERR_LLM),
            history=history,
            warnings=last.warnings,
        ))

    # ------------------------------------------------------------------

    def _finish(self, outcome: CorrectionOutcome) -> CorrectionOutcome:
        self.metrics.record(outcome)
        return outcome

    def _execute_with_timeout(self, sql: str) -> tuple[pd.DataFrame | None, str | None]:
        """Thực thi read-only, ngắt truy vấn nếu vượt quá timeout."""
        try:
            conn = duckdb.connect(str(self.db_path), read_only=True)
        except Exception as e:
            return None, f"Connection Error: {e}"

        timed_out = threading.Event()

        def _interrupt() -> None:
            timed_out.set()
            try:
                conn.interrupt()
            except Exception:
                pass

        timer = threading.Timer(self.timeout_seconds, _interrupt)
        timer.daemon = True
        timer.start()
        try:
            df = conn.execute(sql).fetchdf()
            return df, None
        except Exception as e:
            if timed_out.is_set():
                return None, f"Timeout: truy vấn vượt quá {self.timeout_seconds:.0f}s và đã bị ngắt."
            prefix = "DuckDB Error" if isinstance(e, duckdb.Error) else "Execution Error"
            return None, f"{prefix}: {e}"
        finally:
            timer.cancel()
            conn.close()
