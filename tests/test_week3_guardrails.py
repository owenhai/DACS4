"""Unit tests Tuần 3: SQL Guardrails, Self-Correction Loop và tích hợp pipeline.

Các test chạy offline: LLM được thay bằng FakeLLM trả về phản hồi định sẵn,
còn truy vấn được thực thi thật trên DuckDB.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.prompt_templates import get_few_shot_examples
from src.models.self_correction import (
    ERR_SECURITY,
    ERR_SYNTAX,
    ERR_TIMEOUT,
    ERR_TYPE_MISMATCH,
    ERR_UNKNOWN_COLUMN,
    ERR_UNKNOWN_TABLE,
    CorrectionMetrics,
    SelfCorrectionLoop,
    classify_error,
)
from src.models.sql_guardrails import SQLGuardrails, format_sql, sanitize_sql, validate_sql
from src.models.text_to_sql import TextToSQLPipeline

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "database" / "olist_analytics.duckdb"
requires_db = pytest.mark.skipif(not DB_PATH.exists(), reason="DuckDB database chưa được tạo")


@pytest.fixture(scope="module")
def guard() -> SQLGuardrails:
    return SQLGuardrails()


# ===========================================================================
# 3.1 Guardrails - câu hợp lệ
# ===========================================================================

@pytest.mark.parametrize("example", get_few_shot_examples(), ids=lambda e: e["question"][:30])
def test_few_shot_examples_are_valid(guard, example):
    result = guard.validate_sql(example["sql"])
    assert result.is_valid, result.error_message


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM fact_orders",
    "select count(*) from fact_orders;",
    "SELECT EXTRACT(YEAR FROM d.full_date) AS y, COUNT(*) AS n "
    "FROM fact_orders f JOIN dim_date d ON f.date_key = d.date_key GROUP BY 1",
    "WITH t AS (SELECT price FROM fact_orders) SELECT AVG(price) FROM t",
    "SELECT * FROM fact_orders WHERE order_status = 'delete me; DROP TABLE x'",
    "SELECT * FROM main.fact_orders LIMIT 5",
    "SELECT REPLACE(order_status, 'a', 'b') FROM fact_orders LIMIT 5",
    "SELECT * FROM generate_series(1, 3)",
])
def test_valid_queries(guard, sql):
    result = guard.validate_sql(sql)
    assert result.is_valid, result.error_message
    assert result.sanitized_sql


# ===========================================================================
# 3.1 / 3.4 Guardrails - chặn bảo mật
# ===========================================================================

SECURITY_ATTACKS = [
    "DROP TABLE fact_orders",
    "DELETE FROM fact_orders",
    "UPDATE fact_orders SET price = 0",
    "INSERT INTO fact_orders SELECT * FROM fact_orders",
    "ALTER TABLE fact_orders ADD COLUMN x INT",
    "CREATE TABLE hack AS SELECT * FROM fact_orders",
    "TRUNCATE fact_orders",
    "SELECT 1; DROP TABLE fact_orders",
    "SELECT * FROM fact_orders; DELETE FROM dim_customers",
    "PRAGMA table_info('fact_orders')",
    "ATTACH 'evil.db' AS evil",
    "COPY fact_orders TO 'C:/leak.csv'",
    "INSTALL httpfs",
    "EXEC sp_who",
    "SELECT * FROM read_csv('C:/secret.csv')",
    "SELECT * FROM read_parquet('data/*.parquet')",
    "SELECT * FROM glob('C:/*')",
    "SELECT * FROM duckdb_tables()",
    "SELECT * FROM information_schema.tables",
    "SELECT getenv('GEMINI_API_KEY')",
    "WITH x AS (DELETE FROM fact_orders RETURNING *) SELECT * FROM x",
]


@pytest.mark.parametrize("sql", SECURITY_ATTACKS)
def test_security_attacks_blocked(guard, sql):
    result = guard.validate_sql(sql)
    assert not result.is_valid
    assert result.error_type == ERR_SECURITY
    assert result.is_security_violation


def test_comment_injection_stripped(guard):
    result = guard.validate_sql("SELECT * FROM fact_orders -- ; DROP TABLE fact_orders\nLIMIT 5")
    assert result.is_valid
    assert "--" not in result.sanitized_sql
    assert "DROP" not in result.sanitized_sql.upper()
    assert any("comment" in w for w in result.warnings)


def test_block_comment_stripped(guard):
    result = guard.validate_sql("SELECT /* hidden */ COUNT(*) FROM fact_orders")
    assert result.is_valid
    assert "/*" not in result.sanitized_sql


def test_comment_only_rejected(guard):
    assert not guard.validate_sql("-- just a comment").is_valid


def test_empty_sql_rejected(guard):
    result = guard.validate_sql("   ")
    assert not result.is_valid and result.error_type == ERR_SYNTAX


# ===========================================================================
# Guardrails - bảng / cột / độ phức tạp
# ===========================================================================

def test_unknown_table(guard):
    result = guard.validate_sql("SELECT * FROM users")
    assert not result.is_valid
    assert result.error_type == ERR_UNKNOWN_TABLE
    assert "fact_orders" in result.error_message  # gợi ý bảng hợp lệ cho LLM


def test_unknown_column_with_alias(guard):
    result = guard.validate_sql("SELECT f.not_a_col FROM fact_orders f")
    assert not result.is_valid
    assert result.error_type == ERR_UNKNOWN_COLUMN
    assert "price" in result.error_message  # gợi ý cột hợp lệ


def test_column_on_wrong_table(guard):
    sql = ("SELECT c.price FROM fact_orders f "
           "JOIN dim_customers c ON f.customer_key = c.customer_key")
    result = guard.validate_sql(sql)
    assert not result.is_valid and result.error_type == ERR_UNKNOWN_COLUMN


def test_cte_alias_columns_not_checked(guard):
    sql = "WITH t AS (SELECT price AS p FROM fact_orders) SELECT t.p FROM t"
    assert guard.validate_sql(sql).is_valid


def test_too_many_joins():
    g = SQLGuardrails(max_joins=1)
    sql = ("SELECT 1 FROM fact_orders f JOIN dim_date d ON f.date_key = d.date_key "
           "JOIN dim_products p ON f.product_key = p.product_key")
    result = g.validate_sql(sql)
    assert not result.is_valid and result.error_type == "complexity"


def test_subquery_depth():
    g = SQLGuardrails(max_subquery_depth=1)
    sql = ("SELECT * FROM fact_orders WHERE price > (SELECT AVG(price) FROM fact_orders "
           "WHERE price > (SELECT MIN(price) FROM fact_orders))")
    result = g.validate_sql(sql)
    assert not result.is_valid and result.error_type == "complexity"


def test_sql_too_long():
    g = SQLGuardrails(max_length=50)
    assert g.validate_sql("SELECT " + ", ".join(["price"] * 30) + " FROM fact_orders").error_type == "complexity"


# ===========================================================================
# sanitize_sql / LIMIT / format
# ===========================================================================

def test_default_limit_added(guard):
    result = guard.validate_sql("SELECT * FROM fact_orders")
    assert result.sanitized_sql.rstrip().endswith(f"LIMIT {guard.default_limit}")


def test_existing_limit_kept(guard):
    result = guard.validate_sql("SELECT * FROM fact_orders LIMIT 10")
    assert result.sanitized_sql.upper().count("LIMIT") == 1
    assert result.sanitized_sql.rstrip().endswith("LIMIT 10")


def test_large_limit_capped(guard):
    result = guard.validate_sql("SELECT * FROM fact_orders LIMIT 999999")
    assert f"LIMIT {guard.max_limit}" in result.sanitized_sql
    assert "999999" not in result.sanitized_sql


def test_subquery_limit_does_not_count_as_top_level(guard):
    sql = "SELECT * FROM (SELECT * FROM fact_orders LIMIT 5) t"
    result = guard.validate_sql(sql)
    assert result.sanitized_sql.rstrip().endswith(f"LIMIT {guard.default_limit}")


def test_module_level_helpers():
    assert validate_sql("SELECT COUNT(*) FROM fact_orders").is_valid
    cleaned = sanitize_sql("SELECT * FROM fact_orders; -- hi")
    assert ";" not in cleaned and "--" not in cleaned and "LIMIT" in cleaned
    assert "SELECT" in format_sql("select price from fact_orders")


# ===========================================================================
# 3.2 Phân loại lỗi
# ===========================================================================

@pytest.mark.parametrize("message,expected", [
    ('Parser Error: syntax error at or near "FORM"', ERR_SYNTAX),
    ("Catalog Error: Table with name users does not exist!", ERR_UNKNOWN_TABLE),
    ('Binder Error: Referenced column "pricee" not found in FROM clause!', ERR_UNKNOWN_COLUMN),
    ("Conversion Error: Could not convert string 'abc' to INT32", ERR_TYPE_MISMATCH),
    ("Binder Error: No function matches the given name and argument types", ERR_TYPE_MISMATCH),
    ("Timeout: truy vấn vượt quá 30s và đã bị ngắt.", ERR_TIMEOUT),
    ("INTERRUPT Error: Interrupted!", ERR_TIMEOUT),
])
def test_classify_error(message, expected):
    assert classify_error(message) == expected


# ===========================================================================
# 3.2 Self-Correction Loop (DuckDB thật + LLM giả)
# ===========================================================================

class ScriptedGenerator:
    """Giả lập LLM: trả lần lượt các SQL định sẵn, ghi lại prompt nhận được."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise RuntimeError("Hết phản hồi giả lập")
        return self.responses.pop(0)


def make_loop(responses, **kwargs) -> tuple[SelfCorrectionLoop, ScriptedGenerator]:
    gen = ScriptedGenerator(responses)
    loop = SelfCorrectionLoop(
        db_path=DB_PATH, sql_generator=gen, schema_text="<schema>", **kwargs
    )
    return loop, gen


@requires_db
def test_attempt_execution_success():
    loop, _ = make_loop([])
    result = loop.attempt_execution("SELECT COUNT(*) AS n FROM fact_orders")
    assert result.success and result.dataframe.iloc[0]["n"] > 0
    assert result.execution_time_ms >= 0


@requires_db
def test_attempt_execution_blocks_before_running():
    loop, _ = make_loop([])
    result = loop.attempt_execution("DROP TABLE fact_orders")
    assert not result.success and result.error_type == ERR_SECURITY
    assert result.error_message.startswith("Guardrails")


@requires_db
def test_first_try_success_no_llm_call():
    loop, gen = make_loop([])
    outcome = loop.run_with_correction("q", "SELECT COUNT(*) AS n FROM fact_orders")
    assert outcome.success and outcome.attempts == 1 and outcome.corrections == 0
    assert gen.prompts == []


@requires_db
def test_corrects_syntax_error():
    loop, gen = make_loop(["SELECT COUNT(*) AS n FROM fact_orders"])
    outcome = loop.run_with_correction("Có bao nhiêu dòng?", "SELEC COUNT(*) FORM fact_orders")
    assert outcome.success and outcome.corrections == 1
    assert outcome.history[0]["error_type"] == ERR_SYNTAX
    # Prompt sửa lỗi phải chứa SQL lỗi, thông báo lỗi và gợi ý theo loại lỗi
    assert "SELEC COUNT" in gen.prompts[0]
    assert "syntax" in gen.prompts[0]
    assert "Gợi ý" in gen.prompts[0]


@requires_db
def test_corrects_unknown_column_from_guardrails():
    loop, gen = make_loop(["SELECT ROUND(SUM(f.price), 2) AS revenue FROM fact_orders f"])
    outcome = loop.run_with_correction("Doanh thu?", "SELECT SUM(f.revenue) FROM fact_orders f")
    assert outcome.success and outcome.corrections == 1
    assert outcome.history[0]["error_type"] == ERR_UNKNOWN_COLUMN
    assert "price" in gen.prompts[0]  # danh sách cột hợp lệ được gửi cho LLM


@requires_db
def test_corrects_unknown_table():
    loop, _ = make_loop(["SELECT COUNT(*) FROM dim_customers"])
    outcome = loop.run_with_correction("Số khách hàng?", "SELECT COUNT(*) FROM customers")
    assert outcome.success
    assert outcome.history[0]["error_type"] == ERR_UNKNOWN_TABLE


@requires_db
def test_corrects_type_mismatch():
    loop, _ = make_loop(["SELECT COUNT(*) FROM fact_orders WHERE date_key >= 20180101"])
    outcome = loop.run_with_correction(
        "Đơn từ 2018?", "SELECT COUNT(*) FROM fact_orders WHERE date_key >= 'abc'"
    )
    assert outcome.success
    assert outcome.history[0]["error_type"] == ERR_TYPE_MISMATCH


@requires_db
def test_security_violation_stops_immediately():
    loop, gen = make_loop(["SELECT 1"])
    outcome = loop.run_with_correction("Xóa hết đơn hàng", "DELETE FROM fact_orders")
    assert not outcome.success and outcome.error_type == ERR_SECURITY
    assert gen.prompts == []  # không nhờ LLM "lách" guardrails


@requires_db
def test_gives_up_after_max_retries():
    loop, gen = make_loop(["SELEC 1", "SELEC 2", "SELEC 3"], max_retries=2)
    outcome = loop.run_with_correction("q", "SELEC 0")
    assert not outcome.success
    assert outcome.attempts == 3 and len(gen.prompts) == 2


@requires_db
def test_llm_failure_during_correction():
    loop, _ = make_loop([])  # generator raises immediately
    outcome = loop.run_with_correction("q", "SELEC 0")
    assert not outcome.success
    assert outcome.history[-1]["error_type"] == "llm_error"


@requires_db
def test_empty_result_warning_and_retry():
    empty_sql = "SELECT * FROM fact_orders WHERE order_status = 'no_such_status'"
    loop, _ = make_loop([])
    outcome = loop.run_with_correction("q", empty_sql)
    assert outcome.success and any("0 dòng" in w for w in outcome.warnings)

    loop2, gen2 = make_loop(["SELECT COUNT(*) FROM fact_orders"], retry_on_empty=True)
    outcome2 = loop2.run_with_correction("q", empty_sql)
    assert outcome2.success and outcome2.corrections == 1
    assert outcome2.history[0]["error_type"] == "empty_result"
    assert len(gen2.prompts) == 1


@requires_db
def test_timeout_interrupts_slow_query():
    loop, _ = make_loop([], timeout_seconds=0.5, max_retries=0)
    slow = ("SELECT COUNT(*) FROM fact_orders a JOIN fact_orders b ON a.price >= b.price "
            "JOIN fact_orders c ON b.price >= c.price")
    outcome = loop.run_with_correction("q", slow)
    assert not outcome.success
    assert outcome.error_type == ERR_TIMEOUT


@requires_db
def test_metrics_and_to_dict():
    loop, _ = make_loop(["SELECT 1 AS x", "SELEC", "SELEC"], max_retries=1)
    loop.run_with_correction("ok", "SELECT 1 AS x")              # thành công ngay
    loop.run_with_correction("fixed", "SELEC 1")                 # sửa thành công
    loop.run_with_correction("blocked", "DROP TABLE fact_orders")  # bị chặn
    out = loop.run_with_correction("fail", "SELEC 9")            # thất bại
    s = loop.metrics.summary()
    assert s["total_queries"] == 4
    assert s["first_try_success"] == 1
    assert s["corrected_success"] == 1
    assert s["blocked_security"] == 1
    assert s["failed"] == 2
    assert s["correction_success_rate"] == 0.5
    d = out.to_dict()
    assert d["success"] is False and d["attempts"] == 2 and "history" in d


def test_metrics_empty():
    assert CorrectionMetrics().summary()["correction_success_rate"] == 0.0


# ===========================================================================
# 3.3 Tích hợp pipeline - 15 câu hỏi end-to-end (LLM giả)
# ===========================================================================

class FakeLLM:
    """Thay GeminiClient: map câu hỏi -> danh sách phản hồi (lần đầu, các lần sửa)."""

    def __init__(self, script: dict[str, list[str]]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = 0

    def generate(self, prompt: str, **_kwargs) -> str:
        self.calls += 1
        for question, responses in self.script.items():
            if question in prompt and responses:
                return responses.pop(0)
        raise RuntimeError("FakeLLM: không có phản hồi cho prompt")


E2E_CASES = [
    # (câu hỏi, [phản hồi LLM...], kỳ vọng thành công, loại lỗi cuối)
    ("Q01 tổng số đơn", ["```sql\nSELECT COUNT(DISTINCT order_id) AS n FROM fact_orders;\n```"], True, None),
    ("Q02 tổng doanh thu", ["SELECT ROUND(SUM(price), 2) AS revenue FROM fact_orders"], True, None),
    ("Q03 điểm review TB", ["SELECT ROUND(AVG(review_score), 2) AS s FROM fact_orders"], True, None),
    ("Q04 doanh thu theo bang",
     ["SELECT c.customer_state, SUM(f.price) AS r FROM fact_orders f JOIN dim_customers c "
      "ON f.customer_key = c.customer_key GROUP BY 1 ORDER BY 2 DESC"], True, None),
    ("Q05 theo năm",
     ["SELECT d.year, COUNT(*) AS n FROM fact_orders f JOIN dim_date d ON f.date_key = d.date_key GROUP BY 1"],
     True, None),
    ("Q06 lỗi cú pháp",
     ["SELEC COUNT(*) FORM fact_orders", "SELECT COUNT(*) AS n FROM fact_orders"], True, None),
    ("Q07 sai tên cột",
     ["SELECT SUM(f.revenue) FROM fact_orders f", "SELECT SUM(f.price) FROM fact_orders f"], True, None),
    ("Q08 sai tên bảng",
     ["SELECT COUNT(*) FROM orders", "SELECT COUNT(*) FROM fact_orders"], True, None),
    ("Q09 sai kiểu",
     ["SELECT COUNT(*) FROM fact_orders WHERE date_key > 'x'",
      "SELECT COUNT(*) FROM fact_orders WHERE date_key > 20170101"], True, None),
    ("Q10 sửa 2 lần",
     ["SELEC 1", "SELECT f.nope FROM fact_orders f", "SELECT COUNT(*) FROM fact_orders"], True, None),
    ("Q11 yêu cầu xóa dữ liệu", ["DELETE FROM fact_orders"], False, ERR_SECURITY),
    ("Q12 injection nhiều lệnh", ["SELECT 1; DROP TABLE fact_orders"], False, ERR_SECURITY),
    ("Q13 đọc file", ["SELECT * FROM read_csv('C:/Windows/win.ini')"], False, ERR_SECURITY),
    ("Q14 sửa mãi không được", ["SELEC 1", "SELEC 2", "SELEC 3", "SELEC 4"], False, ERR_SYNTAX),
    ("Q15 CTE phần trăm",
     ["WITH t AS (SELECT COUNT(*) AS total FROM fact_orders) "
      "SELECT f.order_status, ROUND(100.0 * COUNT(*) / t.total, 2) AS pct "
      "FROM fact_orders f CROSS JOIN t GROUP BY f.order_status, t.total"], True, None),
]


@pytest.fixture
def make_pipeline():
    def _make(script):
        llm = FakeLLM(script)
        return TextToSQLPipeline(db_path=DB_PATH, llm_client=llm, max_corrections=3), llm
    return _make


@requires_db
@pytest.mark.parametrize("question,responses,expect_ok,expect_err", E2E_CASES, ids=[c[0][:3] for c in E2E_CASES])
def test_pipeline_end_to_end(make_pipeline, question, responses, expect_ok, expect_err):
    pipeline, llm = make_pipeline({question: responses})
    result = pipeline.run(question)
    assert result.success is expect_ok, result.error_message
    if expect_ok:
        assert result.dataframe is not None and len(result.dataframe) > 0
        assert "LIMIT" in result.generated_sql.upper()
    else:
        assert result.error_type == expect_err
    if expect_err == ERR_SECURITY:
        assert llm.calls == 1  # chỉ lần sinh đầu tiên, không gọi LLM để sửa
        assert "bảo mật" in result.error_message


@requires_db
def test_pipeline_metrics_accumulate(make_pipeline):
    pipeline, _ = make_pipeline({
        "A?": ["SELECT 1 AS x"],
        "B?": ["SELEC 1", "SELECT 2 AS y"],
    })
    pipeline.ask("A?")
    pipeline.ask("B?")
    m = pipeline.metrics
    assert m["total_queries"] == 2 and m["corrected_success"] == 1


@requires_db
def test_pipeline_execute_sql_goes_through_guardrails(make_pipeline):
    pipeline, _ = make_pipeline({})
    df, err = pipeline._execute_sql("DROP TABLE fact_orders")
    assert df is None and "Guardrails" in err
    # Database vẫn còn nguyên
    df, err = pipeline._execute_sql("SELECT COUNT(*) AS n FROM fact_orders")
    assert err is None and df.iloc[0]["n"] > 0
