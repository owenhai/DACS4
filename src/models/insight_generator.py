"""Insight Generation: tóm tắt kết quả truy vấn thành 3-5 nhận xét tiếng Việt.

Thiết kế 2 bước để hạn chế LLM bịa số liệu:
1. ``compute_statistics``: pandas tính sẵn tổng, trung bình, min/max, xu hướng,
   so sánh nhóm, outlier (IQR) - các con số luôn chính xác.
2. ``generate_insights``: LLM diễn đạt lại các con số thành nhận xét.
   Nếu LLM lỗi/không có, dùng nhận xét sinh bằng luật từ thống kê (fallback).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import pandas as pd

from src.models.prompt_templates import build_insight_prompt
from src.visualization.chart_classifier import (
    ROLE_CATEGORICAL,
    ROLE_DATETIME,
    ROLE_NUMERIC,
    ROLE_TEMPORAL,
    ChartSpec,
    classify_chart_type,
)

logger = logging.getLogger(__name__)

PREVIEW_ROWS = 15
MAX_BULLETS = 5


class _LLM(Protocol):
    def generate(self, prompt: str, **kwargs: Any) -> str: ...


@dataclass
class InsightResult:
    """Kết quả sinh insight.

    Attributes:
        bullets: Danh sách nhận xét (3-5 câu).
        statistics: Thống kê đã tính bằng pandas.
        source: "llm" hoặc "rule" (fallback khi LLM lỗi).
        error: Lỗi LLM (nếu có).
    """

    bullets: list[str]
    statistics: dict[str, Any] = field(default_factory=dict)
    source: str = "rule"
    error: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(f"- {b}" for b in self.bullets)


# ===========================================================================
# Định dạng số kiểu Việt Nam
# ===========================================================================

def fmt_number(value: Any, decimals: int = 2) -> str:
    """1234567.891 -> '1.234.567,89'; số nguyên không có phần thập phân."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num.is_integer():
        text = f"{int(num):,}"
    else:
        text = f"{num:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _fmt_pct(value: float) -> str:
    return f"{fmt_number(round(value, 1), 1)}%"


# ===========================================================================
# Thống kê tự động
# ===========================================================================

def compute_statistics(
    df: pd.DataFrame,
    spec: ChartSpec | None = None,
    question: str = "",
) -> dict[str, Any]:
    """Tính thống kê cơ bản phục vụ sinh insight.

    Returns:
        Dict gồm: row_count, metrics (theo cột số), trend (nếu có thời gian),
        groups (nếu có cột phân loại), outliers.
    """
    stats: dict[str, Any] = {"row_count": int(len(df))}
    if df is None or df.empty:
        return stats

    spec = spec or classify_chart_type(df, question=question)
    roles = spec.roles
    numeric = [c for c, r in roles.items() if r == ROLE_NUMERIC]
    if not numeric and spec.y:
        numeric = [spec.y]
    categorical = [c for c, r in roles.items() if r == ROLE_CATEGORICAL]
    time_cols = [c for c, r in roles.items() if r in (ROLE_DATETIME, ROLE_TEMPORAL)]

    metrics: dict[str, dict[str, Any]] = {}
    for col in numeric:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        metrics[col] = {
            "sum": float(s.sum()),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "min": float(s.min()),
            "max": float(s.max()),
            "count": int(s.count()),
        }
    stats["metrics"] = metrics

    primary = spec.y if spec.y in metrics else (numeric[0] if numeric and numeric[0] in metrics else None)
    stats["primary_metric"] = primary
    if primary is None or len(df) < 2:
        return stats

    label_col = spec.x if spec.x in categorical else (categorical[0] if categorical else None)

    # Xu hướng theo thời gian
    time_col = spec.x if spec.x in time_cols else (time_cols[0] if time_cols else None)
    if time_col is not None and not spec.color:
        series = df[[time_col, primary]].dropna().sort_values(time_col)
        if len(series) >= 2:
            first, last = float(series[primary].iloc[0]), float(series[primary].iloc[-1])
            peak = series.loc[series[primary].idxmax()]
            low = series.loc[series[primary].idxmin()]
            change_pct = (last - first) / abs(first) * 100 if first else None
            # Hệ số góc chuẩn hóa để xác định hướng tổng thể
            y = series[primary].reset_index(drop=True).astype(float)
            x = pd.Series(range(len(y)), dtype=float)
            slope = float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum())
            rel_slope = slope * len(y) / abs(y.mean()) if y.mean() else 0.0
            direction = "tăng" if rel_slope > 0.1 else "giảm" if rel_slope < -0.1 else "ổn định"
            stats["trend"] = {
                "time_column": time_col,
                "first": {"time": str(series[time_col].iloc[0]), "value": first},
                "last": {"time": str(series[time_col].iloc[-1]), "value": last},
                "change_pct": change_pct,
                "direction": direction,
                "peak": {"time": str(peak[time_col]), "value": float(peak[primary])},
                "low": {"time": str(low[time_col]), "value": float(low[primary])},
            }

    # So sánh nhóm
    if label_col is not None and time_col is None:
        grouped = df[[label_col, primary]].dropna().sort_values(primary, ascending=False)
        total = float(grouped[primary].sum())
        top = grouped.iloc[0]
        bottom = grouped.iloc[-1]
        groups: dict[str, Any] = {
            "label_column": label_col,
            "n_groups": int(grouped[label_col].nunique()),
            "top": {"label": str(top[label_col]), "value": float(top[primary])},
            "bottom": {"label": str(bottom[label_col]), "value": float(bottom[primary])},
        }
        if total > 0 and (grouped[primary] >= 0).all():
            groups["top_share_pct"] = float(top[primary]) / total * 100
            top3 = grouped.head(3)
            groups["top3_share_pct"] = float(top3[primary].sum()) / total * 100
        if float(bottom[primary]) > 0:
            groups["top_vs_bottom_ratio"] = float(top[primary]) / float(bottom[primary])
        stats["groups"] = groups

    # Outlier (IQR)
    s = pd.to_numeric(df[primary], errors="coerce")
    if s.notna().sum() >= 8:
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            hi_mask = s > q3 + 1.5 * iqr
            lo_mask = s < q1 - 1.5 * iqr
            ident = label_col or time_col
            def labels(mask: pd.Series) -> list[str]:
                if ident is None:
                    return [fmt_number(v) for v in s[mask].head(5)]
                return [str(v) for v in df.loc[mask, ident].head(5)]
            stats["outliers"] = {
                "high_count": int(hi_mask.sum()),
                "low_count": int(lo_mask.sum()),
                "high_labels": labels(hi_mask),
                "low_labels": labels(lo_mask),
                "upper_fence": float(q3 + 1.5 * iqr),
            }
    return stats


def format_statistics(stats: dict[str, Any]) -> str:
    """Chuyển thống kê thành văn bản ngắn để đưa vào prompt."""
    lines = [f"- Số dòng kết quả: {fmt_number(stats.get('row_count', 0))}"]
    for col, m in stats.get("metrics", {}).items():
        lines.append(
            f"- {col}: tổng={fmt_number(m['sum'])}, trung bình={fmt_number(m['mean'])}, "
            f"trung vị={fmt_number(m['median'])}, min={fmt_number(m['min'])}, max={fmt_number(m['max'])}"
        )
    if t := stats.get("trend"):
        change = f", thay đổi {_fmt_pct(t['change_pct'])}" if t.get("change_pct") is not None else ""
        lines.append(
            f"- Xu hướng theo {t['time_column']}: {t['direction']}; "
            f"đầu kỳ ({t['first']['time']})={fmt_number(t['first']['value'])}, "
            f"cuối kỳ ({t['last']['time']})={fmt_number(t['last']['value'])}{change}; "
            f"cao nhất tại {t['peak']['time']} ({fmt_number(t['peak']['value'])}), "
            f"thấp nhất tại {t['low']['time']} ({fmt_number(t['low']['value'])})"
        )
    if g := stats.get("groups"):
        line = (
            f"- Theo {g['label_column']} ({g['n_groups']} nhóm): cao nhất là {g['top']['label']} "
            f"({fmt_number(g['top']['value'])}), thấp nhất là {g['bottom']['label']} "
            f"({fmt_number(g['bottom']['value'])})"
        )
        if "top_share_pct" in g:
            line += (f"; nhóm dẫn đầu chiếm {_fmt_pct(g['top_share_pct'])}, "
                     f"top 3 chiếm {_fmt_pct(g['top3_share_pct'])} tổng")
        if "top_vs_bottom_ratio" in g:
            line += f"; gấp {fmt_number(round(g['top_vs_bottom_ratio'], 1), 1)} lần nhóm thấp nhất"
        lines.append(line)
    if o := stats.get("outliers"):
        if o["high_count"] or o["low_count"]:
            parts = []
            if o["high_count"]:
                parts.append(f"{o['high_count']} giá trị cao bất thường ({', '.join(o['high_labels'])})")
            if o["low_count"]:
                parts.append(f"{o['low_count']} giá trị thấp bất thường ({', '.join(o['low_labels'])})")
            lines.append("- Outlier (IQR): " + "; ".join(parts))
    return "\n".join(lines)


# ===========================================================================
# Fallback: insight bằng luật
# ===========================================================================

def rule_based_insights(stats: dict[str, Any]) -> list[str]:
    """Sinh nhận xét trực tiếp từ thống kê (không cần LLM)."""
    bullets: list[str] = []
    metrics = stats.get("metrics", {})
    primary = stats.get("primary_metric")
    row_count = stats.get("row_count", 0)

    if row_count == 0:
        return ["Truy vấn không trả về dữ liệu nào phù hợp với câu hỏi."]

    if row_count == 1 and metrics:
        for col, m in list(metrics.items())[:3]:
            bullets.append(f"{col} có giá trị {fmt_number(m['sum'])}.")
        return bullets

    if g := stats.get("groups"):
        b = (f"{g['top']['label']} dẫn đầu về {primary} với {fmt_number(g['top']['value'])}")
        if "top_share_pct" in g:
            b += f", chiếm {_fmt_pct(g['top_share_pct'])} tổng"
        bullets.append(b + ".")
        bullets.append(f"{g['bottom']['label']} thấp nhất với {fmt_number(g['bottom']['value'])}.")
        if "top3_share_pct" in g and g["n_groups"] > 3:
            bullets.append(f"Top 3 nhóm chiếm {_fmt_pct(g['top3_share_pct'])} tổng {primary} "
                           f"trên {g['n_groups']} nhóm.")

    if t := stats.get("trend"):
        b = f"{primary} có xu hướng {t['direction']} theo {t['time_column']}"
        if t.get("change_pct") is not None:
            b += (f", từ {fmt_number(t['first']['value'])} ({t['first']['time']}) đến "
                  f"{fmt_number(t['last']['value'])} ({t['last']['time']}), "
                  f"thay đổi {_fmt_pct(t['change_pct'])}")
        bullets.append(b + ".")
        bullets.append(f"Đỉnh cao nhất tại {t['peak']['time']} ({fmt_number(t['peak']['value'])}), "
                       f"thấp nhất tại {t['low']['time']} ({fmt_number(t['low']['value'])}).")

    if primary and primary in metrics and len(bullets) < MAX_BULLETS:
        m = metrics[primary]
        bullets.append(f"{primary} trung bình {fmt_number(m['mean'])}, dao động từ "
                       f"{fmt_number(m['min'])} đến {fmt_number(m['max'])}.")

    if (o := stats.get("outliers")) and o["high_count"] and len(bullets) < MAX_BULLETS:
        bullets.append(f"Có {o['high_count']} giá trị cao bất thường: {', '.join(o['high_labels'])}.")

    return bullets[:MAX_BULLETS] or [f"Kết quả gồm {fmt_number(row_count)} dòng."]


# ===========================================================================
# Hàm chính
# ===========================================================================

def parse_bullets(text: str) -> list[str]:
    """Tách phản hồi LLM thành danh sách nhận xét."""
    bullets = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line).strip()
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)  # bỏ in đậm markdown
        if line and not line.endswith(":"):
            bullets.append(line)
    return bullets[:MAX_BULLETS]


def generate_insights(
    question: str,
    sql: str,
    df: pd.DataFrame,
    llm_client: _LLM | None = None,
    spec: ChartSpec | None = None,
) -> InsightResult:
    """Sinh 3-5 nhận xét tiếng Việt cho kết quả truy vấn.

    Args:
        question: Câu hỏi gốc.
        sql: SQL đã chạy.
        df: DataFrame kết quả.
        llm_client: Client có method ``generate(prompt, ...)``. None -> chỉ dùng luật.
        spec: ChartSpec đã phân loại (tránh phân loại lại).

    Returns:
        InsightResult (``source`` = "llm" hoặc "rule").
    """
    stats = compute_statistics(df, spec, question)
    if df is None or df.empty or llm_client is None:
        return InsightResult(rule_based_insights(stats), stats, "rule")

    prompt = build_insight_prompt(
        user_question=question,
        sql_query=sql,
        query_result_preview=df.head(PREVIEW_ROWS).to_string(index=False, max_colwidth=40),
        row_count=len(df),
        statistics_text=format_statistics(stats),
    )
    try:
        raw = llm_client.generate(prompt=prompt, max_retries=2, retry_delay=1.0)
        bullets = parse_bullets(raw)
        if not bullets:
            raise ValueError("LLM trả về insight rỗng")
        return InsightResult(bullets, stats, "llm")
    except Exception as e:
        logger.warning("Sinh insight bằng LLM thất bại, dùng luật: %s", e)
        return InsightResult(rule_based_insights(stats), stats, "rule", error=str(e))
