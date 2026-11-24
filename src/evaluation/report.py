"""Sinh biểu đồ Plotly, CSV tổng hợp và báo cáo Markdown kết quả benchmark (Tuần 6)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.visualization.chart_generator import COLOR_PALETTE, PRIMARY_COLOR, apply_theme

_DIFF_LABELS = {
    "easy": "Dễ (Easy)",
    "medium": "Trung bình (Medium)",
    "hard": "Khó (Hard)",
    "edge": "Edge Cases",
}

_FAILURE_LABELS = {
    "llm_misunderstanding": "LLM hiểu sai câu hỏi",
    "schema_complexity": "Schema phức tạp",
    "sql_syntax": "Lỗi SQL syntax / kiểu / timeout",
    "api_error": "Lỗi kết nối API Gemini",
    "guardrails_false_positive": "Guardrails chặn nhầm",
}


def _primary_run(benchmark_data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    runs = benchmark_data.get("runs", {})
    if "with_correction" in runs:
        return "with_correction", runs["with_correction"]
    if "no_correction" in runs:
        return "no_correction", runs["no_correction"]
    first_key = next(iter(runs))
    return first_key, runs[first_key]


# ===========================================================================
# Biểu đồ Plotly HTML
# ===========================================================================

def generate_charts(benchmark_data: dict[str, Any], charts_dir: Path) -> list[Path]:
    """Sinh 3 biểu đồ tương tác Plotly HTML vào ``charts_dir``."""
    charts_dir.mkdir(parents=True, exist_ok=True)
    runs = benchmark_data.get("runs", {})
    created: list[Path] = []

    # 1. Accuracy by difficulty (Grouped Bar)
    buckets = [
        ("easy", "Dễ"),
        ("medium", "Trung bình"),
        ("hard", "Khó"),
        ("__query_overall__", "Tổng thể (E+M+H)"),
        ("edge", "Edge Cases"),
    ]
    fig_acc = go.Figure()
    mode_styles = [
        ("no_correction", "Không Self-Correction", "#94A3B8"),
        ("with_correction", "Có Self-Correction", PRIMARY_COLOR),
    ]
    for mode_key, label, color in mode_styles:
        if mode_key not in runs:
            continue
        summary = runs[mode_key]["summary"]
        y_vals = []
        for b_key, _ in buckets:
            if b_key == "__query_overall__":
                y_vals.append(summary["overall_query_ex"]["ex_accuracy_pct"])
            else:
                y_vals.append(summary["by_difficulty"].get(b_key, {}).get("ex_accuracy_pct", 0.0))
        fig_acc.add_trace(
            go.Bar(
                name=label,
                x=[b_label for _, b_label in buckets],
                y=y_vals,
                marker_color=color,
                text=[f"{v:.1f}%" for v in y_vals],
                textposition="outside",
            )
        )
    fig_acc.update_layout(
        barmode="group",
        yaxis={"title": "Execution Accuracy (%)", "range": [0, 112]},
        xaxis_title="Nhóm câu hỏi",
    )
    apply_theme(fig_acc, "So sánh Execution Accuracy (EX) theo độ khó")
    acc_path = charts_dir / "accuracy_by_difficulty.html"
    fig_acc.write_html(str(acc_path), include_plotlyjs="cdn")
    created.append(acc_path)

    # 2. Latency distribution (Histogram + P50/P90/P99)
    p_mode, p_run = _primary_run(benchmark_data)
    items = p_run.get("items", [])
    lat_summary = p_run["summary"]["latency"]
    total_ms = [float(it["execution_time_ms"]) for it in items]
    df_lat = pd.DataFrame({
        "Độ trễ (ms)": total_ms,
        "Độ khó": [_DIFF_LABELS.get(it["difficulty"], it["difficulty"]) for it in items],
    })
    fig_lat = px.histogram(
        df_lat,
        x="Độ trễ (ms)",
        color="Độ khó",
        nbins=min(20, max(8, len(items) // 2)) if items else 10,
        color_discrete_sequence=COLOR_PALETTE,
        barmode="stack",
    )
    tot_stats = lat_summary["total"]
    for p_label, val, line_color in (
        ("P50", tot_stats["p50_ms"], "#0F172A"),
        ("P90", tot_stats["p90_ms"], "#F97316"),
        ("P99", tot_stats["p99_ms"], "#EF4444"),
    ):
        fig_lat.add_vline(
            x=val,
            line_dash="dash",
            line_color=line_color,
            annotation_text=f"{p_label}: {val:.0f}ms",
            annotation_position="top",
        )
    gen_mean = lat_summary["generate_sql"]["mean_ms"]
    exec_mean = lat_summary["execute"]["mean_ms"]
    fig_lat.update_layout(
        yaxis_title="Số lượng truy vấn",
        annotations=[
            *fig_lat.layout.annotations,
            dict(
                text=f"Trung bình: LLM={gen_mean:.0f}ms · DuckDB={exec_mean:.0f}ms ({p_mode})",
                xref="paper", yref="paper", x=0.0, y=-0.16,
                showarrow=False, font={"size": 12, "color": "#475569"},
            ),
        ],
        margin={"b": 80},
    )
    apply_theme(fig_lat, "Phân bố độ trễ End-to-End (P50 / P90 / P99)")
    lat_path = charts_dir / "latency_distribution.html"
    fig_lat.write_html(str(lat_path), include_plotlyjs="cdn")
    created.append(lat_path)

    # 3. Error / outcome breakdown
    outcome_counts: Counter = Counter()
    for it in items:
        if it["ex_match"]:
            outcome_counts["Đạt chuẩn (EX = True)"] += 1
        else:
            cat = it.get("failure_category") or "llm_misunderstanding"
            outcome_counts[_FAILURE_LABELS.get(cat, cat)] += 1
    df_err = pd.DataFrame(
        [{"Phân loại": k, "Số câu": v} for k, v in outcome_counts.items()]
    ).sort_values("Số câu", ascending=True)
    fig_err = px.bar(
        df_err,
        x="Số câu",
        y="Phân loại",
        orientation="h",
        text="Số câu",
        color="Phân loại",
        color_discrete_sequence=COLOR_PALETTE,
    )
    fig_err.update_traces(textposition="outside")
    fig_err.update_layout(showlegend=False, xaxis_title="Số câu hỏi", yaxis_title="")
    apply_theme(fig_err, f"Phân bố kết quả & phân loại lỗi ({p_mode})")
    err_path = charts_dir / "error_breakdown.html"
    fig_err.write_html(str(err_path), include_plotlyjs="cdn")
    created.append(err_path)

    return created


# ===========================================================================
# CSV tổng hợp
# ===========================================================================

def export_summary_csv(benchmark_data: dict[str, Any], csv_path: Path) -> Path:
    """Xuất bảng kết quả chi tiết từng câu hỏi ra CSV (UTF-8 BOM)."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    runs = benchmark_data.get("runs", {})
    mode_maps: dict[str, dict[str, dict[str, Any]]] = {
        mode: {it["id"]: it for it in data.get("items", [])}
        for mode, data in runs.items()
    }
    base_items = next(iter(runs.values())).get("items", []) if runs else []

    rows: list[dict[str, Any]] = []
    for base in base_items:
        qid = base["id"]
        row: dict[str, Any] = {
            "ID": qid,
            "Độ khó": base["difficulty"],
            "Nhóm": base["category"],
            "Câu hỏi": base["question"],
            "Kỳ vọng": base["expected_behavior"],
        }
        for mode, by_id in mode_maps.items():
            it = by_id.get(qid, {})
            row[f"EX ({mode})"] = it.get("ex_match")
            row[f"Thời gian ms ({mode})"] = it.get("execution_time_ms")
            row[f"Tự sửa ({mode})"] = it.get("correction_attempts")
            row[f"Loại lỗi ({mode})"] = it.get("failure_category") or ""
            row[f"Lý do ({mode})"] = it.get("match_reason") or ""
            row[f"SQL ({mode})"] = it.get("generated_sql") or ""
        rows.append(row)

    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
    return csv_path


# ===========================================================================
# Báo cáo Markdown
# ===========================================================================

def generate_markdown_report(
    benchmark_data: dict[str, Any], report_path: Path
) -> Path:
    """Sinh báo cáo thực nghiệm Tuần 6 (``results/BENCHMARK_REPORT.md``)."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    meta = benchmark_data.get("metadata", {})
    runs = benchmark_data.get("runs", {})
    comp = benchmark_data.get("comparison")
    p_mode, p_run = _primary_run(benchmark_data)
    p_sum = p_run["summary"]
    has_both = "no_correction" in runs and "with_correction" in runs

    lines: list[str] = [
        "# 📊 Báo cáo Thực nghiệm & Đánh giá Hiệu năng (Tuần 6)",
        "",
        "## 1. Thiết lập thực nghiệm",
        "",
        f"- **Thời điểm chạy:** `{meta.get('timestamp', '')}`",
        f"- **Mô hình LLM:** `{meta.get('model_name', '')}` (`LLM_CACHE={meta.get('use_cache', False)}`)",
        f"- **Cơ sở dữ liệu:** `{meta.get('db_path', '')}` (DuckDB Star Schema)",
        f"- **Tổng số câu hỏi:** **{meta.get('total_questions', 0)} câu** "
        "(gồm câu chuẩn `query_match` phân cấp độ khó Easy/Medium/Hard và 5 câu `edge` cases)",
        "- **Chỉ số đo đạc:**",
        "  - **Execution Accuracy (EX):** Tỉ lệ câu truy vấn cho kết quả DataFrame khớp với SQL đáp án (ground truth) trong ngưỡng sai số làm tròn, chấp nhận thêm cột phụ ngữ cảnh.",
        "  - **Latency:** Đo riêng thời gian sinh SQL (LLM), thực thi trên DuckDB và tổng thời gian end-to-end (Mean, P50, P90, P99).",
        "",
        "## 2. Tổng hợp Execution Accuracy (EX) theo độ khó",
        "",
    ]

    if has_both:
        no_s = runs["no_correction"]["summary"]
        wi_s = runs["with_correction"]["summary"]
        lines.append(
            "| Nhóm câu hỏi | Số câu | Không Self-Correction | Có Self-Correction | Chênh lệch (điểm %) |"
        )
        lines.append("|---|---:|---:|---:|---:|")
        for key, label in (
            ("easy", "Dễ (Easy)"),
            ("medium", "Trung bình (Medium)"),
            ("hard", "Khó (Hard)"),
        ):
            b = no_s["by_difficulty"].get(key, {})
            n = wi_s["by_difficulty"].get(key, {})
            d = comp["by_difficulty"].get(key, {})
            lines.append(
                f"| {label} | {n.get('total', 0)} | "
                f"{b.get('ex_correct', 0)}/{b.get('total', 0)} ({b.get('ex_accuracy_pct', 0):.1f}%) | "
                f"{n.get('ex_correct', 0)}/{n.get('total', 0)} ({n.get('ex_accuracy_pct', 0):.1f}%) | "
                f"{d.get('abs_diff_pp', 0):+.2f} pp |"
            )
        bq = no_s["overall_query_ex"]
        nq = wi_s["overall_query_ex"]
        dq = comp["query_ex"]
        lines.append(
            f"| **Tổng chuẩn (Easy + Medium + Hard)** | **{nq['total']}** | "
            f"**{bq['ex_correct']}/{bq['total']} ({bq['ex_accuracy_pct']:.1f}%)** | "
            f"**{nq['ex_correct']}/{nq['total']} ({nq['ex_accuracy_pct']:.1f}%)** | "
            f"**{dq['abs_diff_pp']:+.2f} pp** |"
        )
        be = no_s["by_difficulty"].get("edge", {})
        ne = wi_s["by_difficulty"].get("edge", {})
        de = comp["by_difficulty"].get("edge", {})
        lines.append(
            f"| Edge Cases (Bảo mật / Ngoài schema / Rỗng) | {ne.get('total', 0)} | "
            f"{be.get('ex_correct', 0)}/{be.get('total', 0)} ({be.get('ex_accuracy_pct', 0):.1f}%) | "
            f"{ne.get('ex_correct', 0)}/{ne.get('total', 0)} ({ne.get('ex_accuracy_pct', 0):.1f}%) | "
            f"{de.get('abs_diff_pp', 0):+.2f} pp |"
        )
    else:
        lines.append(f"| Nhóm câu hỏi | Số câu | EX ({p_mode}) |")
        lines.append("|---|---:|---:|")
        for key, label in (
            ("easy", "Dễ (Easy)"),
            ("medium", "Trung bình (Medium)"),
            ("hard", "Khó (Hard)"),
            ("edge", "Edge Cases"),
        ):
            row = p_sum["by_difficulty"].get(key, {})
            lines.append(
                f"| {label} | {row.get('total', 0)} | "
                f"{row.get('ex_correct', 0)}/{row.get('total', 0)} ({row.get('ex_accuracy_pct', 0):.1f}%) |"
            )
        oq = p_sum["overall_query_ex"]
        lines.append(
            f"| **Tổng chuẩn (E+M+H)** | **{oq['total']}** | "
            f"**{oq['ex_correct']}/{oq['total']} ({oq['ex_accuracy_pct']:.1f}%)** |"
        )

    lines.extend([
        "",
        f"## 3. Kết quả đo Latency (`{p_mode}`)",
        "",
        "| Thành phần | Mean (ms) | P50 (ms) | P90 (ms) | P99 (ms) | Min–Max (ms) |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for step_key, step_label in (
        ("generate_sql", "Sinh SQL (Gemini Flash)"),
        ("execute", "Thực thi + Guardrails (DuckDB)"),
        ("total", "**Tổng End-to-End**"),
    ):
        st = p_sum["latency"][step_key]
        lines.append(
            f"| {step_label} | {st['mean_ms']:.1f} | {st['p50_ms']:.1f} | "
            f"{st['p90_ms']:.1f} | {st['p99_ms']:.1f} | "
            f"{st['min_ms']:.1f}–{st['max_ms']:.1f} |"
        )

    sc = p_sum["self_correction"]
    lines.extend([
        "",
        "## 4. Đánh giá hiệu quả Self-Correction Loop",
        "",
    ])
    if has_both and comp is not None:
        dq = comp["query_ex"]
        lines.append(
            f"- **So sánh 2 lượt độc lập:** Không Self-Correction đạt **{dq['no_correction_pct']:.2f}%** EX; "
            f"Có Self-Correction đạt **{dq['with_correction_pct']:.2f}%** EX "
            f"(chênh lệch **{dq['abs_diff_pp']:+.2f} điểm %**, tương đối **{dq['rel_improvement_pct']:+.2f}%**)."
        )
    lines.extend([
        f"- **Phân tích nội bộ chế độ `{p_mode}`:**",
        f"  - Tỉ lệ EX ngay ở lần sinh đầu tiên (không cần sửa): **{sc['first_try_query_ex_pct']:.2f}%**",
        f"  - Số truy vấn kích hoạt Self-Correction: **{sc['triggered_count']}** "
        f"(tổng số lượt sửa: **{sc['total_corrections']}**, trung bình **{sc['avg_corrections_per_query']:.3f}** lượt/câu)",
        f"  - Số truy vấn sửa lỗi thực thi thành công: **{sc['recovered_exec_count']}/{sc['triggered_count']}** "
        f"({sc['recovery_rate_pct']:.1f}%), trong đó đạt EX đúng đáp án: **{sc['recovered_ex_count']}**",
        f"  - Loại lỗi đã được sửa: `{sc['recovered_by_error_type'] or 'Không phát sinh lỗi kỹ thuật trong lượt này'}`",
        "",
        f"## 5. Phân tích lỗi chi tiết (`{p_mode}`)",
        "",
    ])

    failed_items = [it for it in p_run.get("items", []) if not it["ex_match"]]
    if not failed_items:
        lines.append("- Không có câu hỏi nào thất bại trong lần chạy này.")
    else:
        fc = p_sum["failure_counts"]
        lines.append("| Nhóm nguyên nhân | Số câu | Tỉ lệ trong số lỗi |")
        lines.append("|---|---:|---:|")
        for cat_key, cnt in sorted(fc.items(), key=lambda kv: -kv[1]):
            pct = cnt / len(failed_items) * 100
            lines.append(
                f"| {_FAILURE_LABELS.get(cat_key, cat_key)} | {cnt} | {pct:.1f}% |"
            )
        lines.extend([
            "",
            "| ID | Độ khó | Câu hỏi | Nguyên nhân | Chi tiết |",
            "|---|---|---|---|---|",
        ])
        for it in failed_items:
            cat_label = _FAILURE_LABELS.get(it["failure_category"] or "", it["failure_category"] or "")
            reason = str(it["match_reason"]).replace("\n", " ").replace("|", "/")[:140]
            q_text = str(it["question"]).replace("|", "/")
            lines.append(f"| {it['id']} | {it['difficulty']} | {q_text} | {cat_label} | {reason} |")

    lines.extend([
        "",
        "## 6. Hạn chế và hướng cải thiện",
        "",
        "- **Phản ứng không tất định của LLM:** Cùng một câu hỏi giữa hai lượt chạy không dùng cache có thể cho cách diễn đạt SQL hơi khác nhau (nhất là câu `hard` có nhiều cách tính tỉ lệ hoặc lọc NULL).",
        "- **Hiểu sai chi tiết nghiệp vụ:** Các câu nhiều bảng (`dim_customers` vs `dim_sellers`) hoặc quy tắc `COUNT(DISTINCT order_id)` trên bảng fact ở mức `order_item` đôi khi dễ nhầm nếu không thêm ví dụ few-shot chuyên biệt.",
        "- **Độ trễ gọi API:** Phần lớn thời gian end-to-end (trên 95%) nằm ở bước gọi LLM, trong khi thực thi DuckDB chỉ tốn vài chục mili-giây.",
        "- **Hướng cải thiện:** Bổ sung few-shot ví dụ cho các câu Window Function / Multi-JOIN, kết hợp cơ chế chọn ví dụ động (Dynamic Few-shot Selection theo câu hỏi đầu vào), và áp dụng semantic cache theo độ tương đồng câu hỏi.",
        "",
        "## 7. Danh mục file kết quả",
        "",
        "- `results/benchmark_results.json`: Dữ liệu JSON đầy đủ từng câu hỏi và thống kê.",
        "- `results/benchmark_summary.csv`: Bảng tổng hợp 40 câu hỏi mở được bằng Excel.",
        "- `results/charts/accuracy_by_difficulty.html`: Biểu đồ so sánh EX theo độ khó.",
        "- `results/charts/latency_distribution.html`: Biểu đồ phân bố độ trễ P50/P90/P99.",
        "- `results/charts/error_breakdown.html`: Biểu đồ phân bố kết quả và phân loại lỗi.",
        "",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
