"""Script chạy đánh giá tự động bộ câu hỏi kiểm thử Tuần 6.

Ví dụ:
    # Kiểm chứng SQL đáp án (không gọi LLM) và điền expected_row_count / preview
    python run_benchmark.py --populate-expected

    # Chạy thực nghiệm đầy đủ so sánh Không vs Có Self-Correction
    python run_benchmark.py --mode compare --model gemini-3.5-flash-lite --delay 0.5
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import duckdb
import pandas as pd

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.evaluation.evaluator import (  # noqa: E402
    aggregate_run_metrics,
    compare_runs,
    evaluate_item,
)
from src.evaluation.report import (  # noqa: E402
    export_summary_csv,
    generate_charts,
    generate_markdown_report,
)
from src.models.llm_client import GeminiClient  # noqa: E402
from src.models.sql_guardrails import SQLGuardrails  # noqa: E402
from src.models.text_to_sql import TextToSQLPipeline  # noqa: E402

# Giữ log console sạch trong khi chạy 40 câu benchmark
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("src.models").setLevel(logging.WARNING)


def _json_safe_records(df: pd.DataFrame, max_rows: int = 10) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in df.head(max_rows).to_dict(orient="records"):
        clean: dict[str, Any] = {}
        for k, v in row.items():
            if pd.isna(v):
                clean[k] = None
            elif hasattr(v, "isoformat"):
                clean[k] = v.isoformat()
            elif hasattr(v, "item"):
                clean[k] = v.item()
            else:
                clean[k] = v
        records.append(clean)
    return records


def populate_expected(questions_path: Path, db_path: Path) -> dict[str, Any]:
    """Kiểm tra SQL đáp án qua Guardrails + DuckDB và điền expected_row_count / preview."""
    payload = json.loads(questions_path.read_text(encoding="utf-8"))
    questions = payload["questions"]
    guard = SQLGuardrails()
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        for q in questions:
            gt_sql = (q.get("ground_truth_sql") or "").strip()
            alts = list(q.get("alt_ground_truth_sql") or [])
            behavior = q.get("expected_behavior", "query_match")

            if not gt_sql:
                q["expected_row_count"] = 0
                q["expected_preview"] = []
                continue

            for idx, sql in enumerate([gt_sql, *alts]):
                val = guard.validate_sql(sql)
                if not val.is_valid:
                    raise ValueError(
                        f"{q['id']} SQL #{idx} bị chặn bởi Guardrails: {val.error_message}"
                    )
                df = conn.execute(sql).fetchdf()
                if behavior == "query_match" and df.empty:
                    raise ValueError(f"{q['id']} SQL #{idx} trả về 0 dòng!")
                if idx == 0:
                    q["expected_row_count"] = int(len(df))
                    q["expected_preview"] = _json_safe_records(df, max_rows=10)
    finally:
        conn.close()

    questions_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Đã kiểm chứng và cập nhật {len(questions)} câu hỏi trong {questions_path}.")
    return payload


def _save_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def run_suite(
    questions_path: Path,
    db_path: Path,
    output_dir: Path,
    model_name: str = "gemini-3.5-flash-lite",
    mode: str = "compare",
    delay: float = 0.5,
    limit: int = 0,
    llm_client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Chạy benchmark theo chế độ ``compare``, ``no_correction`` hoặc ``with_correction``."""
    payload = json.loads(questions_path.read_text(encoding="utf-8"))
    questions: list[dict[str, Any]] = payload["questions"]
    if limit > 0:
        questions = questions[:limit]

    modes_to_run = (
        [("no_correction", 0), ("with_correction", 3)]
        if mode == "compare"
        else [(mode, 0 if mode == "no_correction" else 3)]
    )

    benchmark_data: dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model_name": model_name,
            "use_cache": False,
            "db_path": str(db_path),
            "questions_path": str(questions_path),
            "total_questions": len(questions),
            "mode": mode,
        },
        "runs": {},
        "comparison": None,
    }
    json_path = output_dir / "benchmark_results.json"

    for mode_name, max_corr in modes_to_run:
        print(f"\n=== Chạy chế độ: {mode_name} (max_corrections={max_corr}, n={len(questions)}) ===")
        client = (
            llm_client_factory()
            if llm_client_factory is not None
            else GeminiClient(model_name=model_name, use_cache=False)
        )
        pipeline = TextToSQLPipeline(
            db_path=db_path,
            llm_client=client,
            max_corrections=max_corr,
            enable_chart=False,
            enable_insights=False,
        )

        items: list[dict[str, Any]] = []
        for idx, q_spec in enumerate(questions, start=1):
            res = pipeline.run(q_spec["question"])
            ev = evaluate_item(q_spec, res, db_path)
            items.append(ev)
            status = "OK  " if ev["ex_match"] else f"FAIL ({ev['failure_category']})"
            print(
                f"[{idx:02d}/{len(questions):02d}] {ev['id']} [{ev['difficulty']:6s}] "
                f"{status} | {ev['execution_time_ms'] / 1000:.2f}s | corr={ev['correction_attempts']}",
                flush=True,
            )
            if delay > 0 and idx < len(questions):
                time.sleep(delay)

        summary = aggregate_run_metrics(items)
        benchmark_data["runs"][mode_name] = {
            "max_corrections": max_corr,
            "summary": summary,
            "items": items,
        }
        # Lưu ngay sau mỗi chế độ để tránh mất kết quả nếu gián đoạn giữa chừng
        _save_json(benchmark_data, json_path)

    if "no_correction" in benchmark_data["runs"] and "with_correction" in benchmark_data["runs"]:
        benchmark_data["comparison"] = compare_runs(
            benchmark_data["runs"]["no_correction"]["summary"],
            benchmark_data["runs"]["with_correction"]["summary"],
        )
        _save_json(benchmark_data, json_path)

    export_summary_csv(benchmark_data, output_dir / "benchmark_summary.csv")
    generate_charts(benchmark_data, output_dir / "charts")
    generate_markdown_report(benchmark_data, output_dir / "BENCHMARK_REPORT.md")
    print(f"\nĐã lưu toàn bộ kết quả vào: {output_dir}")
    return benchmark_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy benchmark Text-to-SQL DACS4 (Tuần 6)")
    parser.add_argument("--questions", type=Path, default=_ROOT / "tests" / "test_questions.json")
    parser.add_argument(
        "--db", type=Path, default=_ROOT / "data" / "database" / "olist_analytics.duckdb"
    )
    parser.add_argument("--output-dir", type=Path, default=_ROOT / "results")
    parser.add_argument("--model", type=str, default="gemini-3.5-flash-lite")
    parser.add_argument(
        "--mode", choices=["compare", "no_correction", "with_correction"], default="compare"
    )
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--populate-expected", action="store_true")
    args = parser.parse_args()

    if args.populate_expected:
        populate_expected(args.questions, args.db)
        return

    run_suite(
        questions_path=args.questions,
        db_path=args.db,
        output_dir=args.output_dir,
        model_name=args.model,
        mode=args.mode,
        delay=args.delay,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
