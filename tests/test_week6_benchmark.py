"""Unit tests Tuần 6: kiểm thử bộ 40 câu hỏi, evaluator, comparator, report và run_benchmark."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import duckdb
import pandas as pd
import pytest

import run_benchmark
from src.evaluation.evaluator import (
    aggregate_run_metrics,
    classify_failure,
    compare_dataframes,
    compare_runs,
    compute_latency_stats,
    evaluate_item,
)
from src.evaluation.report import (
    export_summary_csv,
    generate_charts,
    generate_markdown_report,
)
from src.models.sql_guardrails import validate_sql
from src.models.text_to_sql import QueryResult

ROOT_DIR = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = ROOT_DIR / "tests" / "test_questions.json"
DB_PATH = ROOT_DIR / "data" / "database" / "olist_analytics.duckdb"
requires_db = pytest.mark.skipif(not DB_PATH.exists(), reason="DuckDB database chưa được tạo")


# ===========================================================================
# 6.1 Tính toàn vẹn của tests/test_questions.json
# ===========================================================================

@requires_db
def test_questions_json_integrity():
    payload = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    questions = payload["questions"]
    assert len(questions) == 40

    counts = Counter(q["difficulty"] for q in questions)
    assert counts == {"easy": 12, "medium": 12, "hard": 11, "edge": 5}

    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids))

    conn = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        for q in questions:
            gt_sql = q["ground_truth_sql"]
            if q["expected_behavior"] == "query_match":
                assert gt_sql.strip()
                for sql in [gt_sql, *q.get("alt_ground_truth_sql", [])]:
                    assert validate_sql(sql).is_valid, f"{q['id']} bị guardrails chặn: {sql}"
                    df = conn.execute(sql).fetchdf()
                    assert not df.empty, f"{q['id']} trả về 0 dòng"
                df_main = conn.execute(gt_sql).fetchdf()
                assert len(df_main) == q["expected_row_count"]
    finally:
        conn.close()


# ===========================================================================
# 6.2 compare_dataframes, evaluate_item, classify_failure
# ===========================================================================

def test_compare_dataframes_cases():
    gt = pd.DataFrame({"cat": ["a", "b"], "rev": [100.0, 50.0]})

    # Khớp chính xác và sai số nhỏ trong ngưỡng làm tròn
    ok, _ = compare_dataframes(pd.DataFrame({"c": ["A ", "b"], "r": [100.02, 49.98]}), gt, ordered=True)
    assert ok

    # Chấp nhận cột phụ ngữ cảnh kiểu BIRD
    pred_extra = pd.DataFrame({"cat": ["a", "b"], "orders": [10, 5], "rev": [100.0, 50.0]})
    ok, _ = compare_dataframes(pred_extra, gt, ordered=True)
    assert ok

    # Ordered vs unordered
    pred_swapped = pd.DataFrame({"cat": ["b", "a"], "rev": [50.0, 100.0]})
    ok_ord, _ = compare_dataframes(pred_swapped, gt, ordered=True)
    ok_unord, _ = compare_dataframes(pred_swapped, gt, ordered=False)
    assert not ok_ord and ok_unord

    # Lệch số dòng & lệch giá trị
    assert not compare_dataframes(pd.DataFrame({"cat": ["a"], "rev": [100.0]}), gt)[0]
    assert not compare_dataframes(pd.DataFrame({"cat": ["a", "b"], "rev": [100.0, 90.0]}), gt)[0]

    # Scalar 1x1 với cột phụ
    gt_scalar = pd.DataFrame({"total_orders": [98666]})
    pred_scalar = pd.DataFrame({"total_orders": [98666], "total_items": [112650]})
    assert compare_dataframes(pred_scalar, gt_scalar)[0]

    # Cả 2 rỗng
    assert compare_dataframes(pd.DataFrame(), pd.DataFrame())[0]
    assert not compare_dataframes(None, gt)[0]


def test_evaluate_edge_cases(tmp_path):
    # Dummy DB path (không truy vấn vì không phải query_match)
    fake_db = tmp_path / "unused.duckdb"

    # block_or_refuse: guardrails chặn
    q_sec = {"id": "X01", "difficulty": "edge", "question": "Xóa bảng", "expected_behavior": "block_or_refuse"}
    r_blocked = QueryResult(question="Xóa bảng", generated_sql="DELETE FROM fact_orders",
                            success=False, error_type="security", error_message="Blocked")
    assert evaluate_item(q_sec, r_blocked, fake_db)["ex_match"] is True

    # block_or_refuse: LLM tự từ chối bằng SELECT
    r_refuse = QueryResult(
        question="Xóa bảng",
        generated_sql="SELECT 'Error: DDL/DML not allowed. Only SELECT statements.' AS msg",
        dataframe=pd.DataFrame({"msg": ["Error: DDL/DML not allowed. Only SELECT statements."]}),
        success=True,
    )
    assert evaluate_item(q_sec, r_refuse, fake_db)["ex_match"] is True

    # block_or_refuse: trả dữ liệu thật thay vì chặn -> fail
    r_bad = QueryResult(
        question="Xóa bảng", generated_sql="SELECT COUNT(*) FROM fact_orders",
        dataframe=pd.DataFrame({"n": [100]}), success=True,
    )
    assert evaluate_item(q_sec, r_bad, fake_db)["ex_match"] is False

    # handle_gracefully
    q_oos = {"id": "X04", "difficulty": "edge", "question": "Theo nhân viên?", "expected_behavior": "handle_gracefully"}
    r_unk = QueryResult(question="Theo nhân viên?", generated_sql="SELECT e.name FROM emp e",
                        success=False, error_type="unknown_table", error_message="No table")
    assert evaluate_item(q_oos, r_unk, fake_db)["ex_match"] is True

    # empty_or_zero: 0 dòng hoặc 1 dòng toàn 0/NULL
    q_emp = {"id": "X05", "difficulty": "edge", "question": "Năm 2025?", "expected_behavior": "empty_or_zero"}
    assert evaluate_item(q_emp, QueryResult("q", "SELECT 1", pd.DataFrame(), True), fake_db)["ex_match"] is True
    assert evaluate_item(q_emp, QueryResult("q", "SELECT 1", pd.DataFrame({"rev": [None]}), True), fake_db)["ex_match"] is True
    assert evaluate_item(q_emp, QueryResult("q", "SELECT 1", pd.DataFrame({"rev": [50.0]}), True), fake_db)["ex_match"] is False


def test_classify_failure_categories():
    q_easy = {"difficulty": "easy", "question": "Tổng doanh thu?"}
    q_orders = {"difficulty": "medium", "question": "Có bao nhiêu đơn hàng theo bang?"}

    assert classify_failure(q_easy, QueryResult("q", "", success=False, error_message="Loi sinh SQL: 503"), "") == "api_error"
    assert classify_failure(q_easy, QueryResult("q", "SELECT 1", success=False, error_type="llm_error", error_message="504 DEADLINE_EXCEEDED"), "") == "api_error"
    assert classify_failure(q_easy, QueryResult("q", "SELEC", success=False, error_type="syntax"), "") == "sql_syntax"
    assert classify_failure(q_easy, QueryResult("q", "SELECT *", success=False, error_type="unknown_column"), "") == "schema_complexity"
    assert classify_failure(q_orders, QueryResult("q", "SELECT COUNT(*) FROM fact_orders", success=True), "Lệch") == "schema_complexity"
    assert classify_failure(q_easy, QueryResult("q", "SELECT 1", success=True), "Giá trị không khớp") == "llm_misunderstanding"


# ===========================================================================
# 6.3 Tổng hợp metrics, biểu đồ và báo cáo
# ===========================================================================

def test_metrics_and_report_generation(tmp_path):
    assert compute_latency_stats([])["p90_ms"] == 0.0
    lat = compute_latency_stats([100.0, 200.0, 300.0, 400.0, 500.0])
    assert lat["p50_ms"] == 300.0 and lat["mean_ms"] == 300.0

    def _item(qid, diff, ex, lat_ms, corr=0, fail_cat=None, hist=None):
        return {
            "id": qid, "difficulty": diff, "category": "test", "question": f"Câu {qid}",
            "expected_behavior": "edge" if diff == "edge" else "query_match",
            "success": fail_cat not in ("sql_syntax", "api_error"),
            "ex_match": ex, "match_reason": "ok" if ex else "sai",
            "failure_category": fail_cat, "error_type": "syntax" if corr else None,
            "error_message": None, "generated_sql": "SELECT 1",
            "correction_attempts": corr, "correction_history": hist or [],
            "timings_ms": {"generate_sql": lat_ms - 10, "execute": 10.0},
            "execution_time_ms": lat_ms, "row_count": 1,
        }

    no_items = [
        _item("E01", "easy", True, 1000.0),
        _item("H01", "hard", False, 1200.0, fail_cat="sql_syntax"),
        _item("X01", "edge", True, 900.0),
    ]
    with_items = [
        _item("E01", "easy", True, 1000.0),
        _item("H01", "hard", True, 2100.0, corr=1, hist=[{"success": False, "error_type": "syntax"}, {"success": True}]),
        _item("X01", "edge", True, 900.0),
    ]
    no_sum = aggregate_run_metrics(no_items)
    with_sum = aggregate_run_metrics(with_items)
    comp = compare_runs(no_sum, with_sum)
    assert comp["query_ex"]["no_correction_pct"] == 50.0
    assert comp["query_ex"]["with_correction_pct"] == 100.0
    assert comp["query_ex"]["abs_diff_pp"] == 50.0
    assert with_sum["self_correction"]["recovered_by_error_type"] == {"syntax": 1}

    benchmark_data = {
        "metadata": {
            "timestamp": "2026-11-24 18:00:00",
            "model_name": "gemini-3.5-flash-lite",
            "use_cache": False,
            "db_path": "olist_analytics.duckdb",
            "total_questions": 3,
        },
        "runs": {
            "no_correction": {"max_corrections": 0, "summary": no_sum, "items": no_items},
            "with_correction": {"max_corrections": 3, "summary": with_sum, "items": with_items},
        },
        "comparison": comp,
    }
    charts = generate_charts(benchmark_data, tmp_path / "charts")
    assert len(charts) == 3 and all(p.exists() for p in charts)

    csv_path = export_summary_csv(benchmark_data, tmp_path / "summary.csv")
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")

    md_path = generate_markdown_report(benchmark_data, tmp_path / "REPORT.md")
    md_text = md_path.read_text(encoding="utf-8")
    assert "Execution Accuracy" in md_text and "P99" in md_text and "Self-Correction" in md_text


@requires_db
def test_run_benchmark_offline_mock(tmp_path):
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
    picked = [
        next(q for q in questions if q["id"] == qid)
        for qid in ("E01", "M01", "H01", "X01")
    ]
    q_file = tmp_path / "mini_questions.json"
    q_file.write_text(json.dumps({"questions": picked}, ensure_ascii=False), encoding="utf-8")

    # Giả lập H01 lỗi cú pháp ở lần đầu, sửa đúng ở lần 2
    class MiniLLM:
        def __init__(self):
            self.h01_calls = 0

        def generate(self, prompt: str, **_kw) -> str:
            for q in picked:
                if q["question"] in prompt:
                    if q["id"] == "H01":
                        self.h01_calls += 1
                        if self.h01_calls == 1:
                            return "SELEC month FROM dim_date"
                        return q["ground_truth_sql"]
                    if q["id"] == "X01":
                        return "DELETE FROM fact_orders"
                    return q["ground_truth_sql"]
            raise RuntimeError("no match")

    out_dir = tmp_path / "results"
    data = run_benchmark.run_suite(
        questions_path=q_file,
        db_path=DB_PATH,
        output_dir=out_dir,
        model_name="fake-llm",
        mode="compare",
        delay=0.0,
        llm_client_factory=MiniLLM,
    )
    assert data["comparison"]["query_ex"]["no_correction_pct"] == 66.67
    assert data["comparison"]["query_ex"]["with_correction_pct"] == 100.0
    assert (out_dir / "benchmark_results.json").exists()
    assert (out_dir / "benchmark_summary.csv").exists()
    assert (out_dir / "BENCHMARK_REPORT.md").exists()
    assert len(list((out_dir / "charts").glob("*.html"))) == 3
