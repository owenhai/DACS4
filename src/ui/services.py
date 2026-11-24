"""Các hàm xử lý và định dạng dữ liệu thuần Python cho giao diện Streamlit.

Tách riêng khỏi ``app.py`` và không import ``streamlit`` để có thể viết unit
test độc lập và dễ mock khi chạy ``AppTest``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.data.schema_metadata import get_schema_metadata, get_table_relationships
from src.models.llm_client import GeminiClient
from src.models.sql_guardrails import BLACKLISTED_KEYWORDS, BLOCKED_FUNCTIONS
from src.models.text_to_sql import QueryResult, TextToSQLPipeline

DEFAULT_MODEL = "gemini-3.5-flash-lite"
MAX_QUESTION_LENGTH = 500
DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "database"
    / "olist_analytics.duckdb"
)

MODEL_OPTIONS: dict[str, str] = {
    "gemini-3.5-flash-lite": "3.5 Flash Lite · Nhanh",
    "gemini-3.5-flash": "3.5 Flash · Cân bằng",
    "gemini-3.8-flash": "3.8 Flash · Nâng cao",
}

EXAMPLE_QUESTIONS: list[str] = [
    "Tổng số đơn hàng là bao nhiêu?",
    "Top 5 danh mục sản phẩm có doanh thu cao nhất?",
    "Doanh thu theo từng tháng năm 2017?",
    "Tỉ lệ phần trăm đơn hàng theo phương thức thanh toán?",
]

CHART_TYPE_LABELS: dict[str, tuple[str, str]] = {
    "bar": ("📊", "Biểu đồ cột"),
    "line": ("📈", "Biểu đồ đường"),
    "pie": ("🥧", "Biểu đồ tròn"),
    "scatter": ("🔵", "Biểu đồ phân tán"),
    "histogram": ("📶", "Phân phối"),
    "grouped_bar": ("📊", "Cột nhóm"),
    "map": ("🗺️", "Bản đồ"),
    "kpi": ("🎯", "Thẻ KPI"),
    "table": ("📋", "Bảng dữ liệu"),
}

CATEGORIZED_EXAMPLES: list[dict[str, str]] = [
    {
        "category": "Tổng quan KPI",
        "icon": "🎯",
        "question": "Tổng số đơn hàng là bao nhiêu?",
    },
    {
        "category": "Top doanh thu",
        "icon": "🏆",
        "question": "Top 5 danh mục sản phẩm có doanh thu cao nhất?",
    },
    {
        "category": "Xu hướng tháng",
        "icon": "📈",
        "question": "Doanh thu theo từng tháng năm 2017?",
    },
]

GUARDRAILS_SUMMARY: list[tuple[str, str]] = [
    (
        "Whitelist SELECT-only",
        "Chỉ cho phép câu lệnh SELECT và CTE (WITH ... SELECT); chặn mọi lệnh thay đổi dữ liệu.",
    ),
    (
        "Blacklist từ khóa nguy hiểm",
        f"Chặn {len(BLACKLISTED_KEYWORDS)} từ khóa DDL/DML/hệ thống "
        "(DROP, DELETE, UPDATE, INSERT, ALTER, PRAGMA, COPY...).",
    ),
    (
        "Chặn đọc file & Stacked Queries",
        f"Chặn nhiều câu lệnh nối dấu ';', comment injection (--, /* */) và "
        f"{len(BLOCKED_FUNCTIONS)} hàm đọc file (read_csv, glob...).",
    ),
    (
        "Kiểm tra Schema & Độ phức tạp",
        "Chỉ cho phép 6 bảng trong Star Schema, kiểm tra alias.column, "
        "tối đa 8 JOIN và subquery sâu 3 tầng.",
    ),
    (
        "Tự động giới hạn kết quả & Timeout",
        "Tự thêm LIMIT 1000 (tối đa 10.000) và ngắt truy vấn DuckDB chạy quá 30 giây.",
    ),
    (
        "Self-Correction Loop (tối đa 3 lần)",
        "Phân loại lỗi (cú pháp, sai bảng/cột, sai kiểu, timeout) để gửi gợi ý "
        "cho LLM tự sửa; dừng ngay nếu vi phạm bảo mật.",
    ),
]

PIPELINE_STEPS: dict[str, str] = {
    "generate_sql": "Đang sinh SQL bằng Gemini...",
    "execute": "Đang kiểm duyệt & thực thi SQL trên DuckDB...",
    "chart": "Đang tạo biểu đồ...",
    "insight": "Đang viết nhận xét...",
    "done": "Hoàn tất",
}

_TIMING_LABELS: list[tuple[str, str]] = [
    ("generate_sql", "Sinh SQL"),
    ("execute", "Thực thi"),
    ("chart", "Biểu đồ"),
    ("insight", "Nhận xét"),
]

_LOG_COLUMNS = ["Thời gian", "Câu hỏi", "Trạng thái", "Biểu đồ", "Tự sửa", "Tổng (s)"]


def validate_question(text: str | None) -> tuple[bool, str | None, str]:
    """Kiểm tra câu hỏi đầu vào của người dùng.

    Args:
        text: Chuỗi câu hỏi thô.

    Returns:
        Tuple ``(hợp_lệ, thông_báo_lỗi, câu_hỏi_đã_strip)``.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return False, "Vui lòng nhập câu hỏi.", ""
    if len(cleaned) > MAX_QUESTION_LENGTH:
        return False, f"Câu hỏi quá dài (tối đa {MAX_QUESTION_LENGTH} ký tự).", cleaned
    return True, None, cleaned


def build_pipeline(
    model_name: str,
    use_cache: bool,
    max_corrections: int,
    enable_insights: bool,
) -> TextToSQLPipeline:
    """Khởi tạo ``TextToSQLPipeline`` theo cấu hình từ giao diện.

    Để ``ValueError`` (thiếu API key) và ``FileNotFoundError`` (thiếu DB)
    tự nổi lên cho ``app.py`` hiển thị hướng dẫn cài đặt.
    """
    client = GeminiClient(model_name=model_name, use_cache=use_cache)
    return TextToSQLPipeline(
        llm_client=client,
        max_corrections=max_corrections,
        enable_insights=enable_insights,
    )


def friendly_error(result: QueryResult | Any) -> tuple[str, str]:
    """Chuyển lỗi kỹ thuật trong ``QueryResult`` thành thông báo dễ hiểu.

    Returns:
        Tuple ``(mức_độ, thông_báo)`` với mức độ là ``error``, ``warning`` hoặc ``info``.
    """
    err_type = getattr(result, "error_type", None)
    err_msg = getattr(result, "error_message", None) or "Lỗi không xác định."
    attempts = getattr(result, "correction_attempts", 0) or 0

    if err_type == "security":
        return (
            "error",
            "🔒 Truy vấn bị chặn vì lý do bảo mật: hệ thống chỉ cho phép đọc dữ liệu (SELECT). "
            f"Chi tiết: {err_msg}",
        )
    if str(err_msg).startswith("Loi sinh SQL"):
        return (
            "warning",
            "Không kết nối được Gemini (có thể đang quá tải). "
            "Hãy thử lại hoặc đổi model ở thanh bên.",
        )
    if err_type == "timeout":
        return (
            "warning",
            "Truy vấn chạy quá lâu và đã bị ngắt. Hãy thử thu hẹp phạm vi câu hỏi "
            "(ví dụ lọc theo năm hoặc giới hạn top N).",
        )
    return (
        "error",
        f"Không trả lời được câu hỏi sau {attempts} lần tự sửa: {err_msg}",
    )


def format_timings(
    timings_ms: dict[str, float] | None, total_ms: float | None
) -> list[tuple[str, str]]:
    """Định dạng thời gian từng bước và tổng thời gian sang giây."""
    items: list[tuple[str, str]] = []
    timings = timings_ms or {}
    for key, label in _TIMING_LABELS:
        if key in timings and timings[key] is not None:
            items.append((label, f"{float(timings[key]) / 1000:.2f}s"))
    if total_ms is not None:
        items.append(("Tổng", f"{float(total_ms) / 1000:.2f}s"))
    return items


def format_compact_number(
    value: float | int | None, prefix: str = "", decimals: int = 2
) -> str:
    """Định dạng số ngắn gọn kiểu Việt Nam cho thẻ KPI.

    - ``>= 1.000.000`` -> ``{prefix}13,59M``
    - Số nguyên -> ``98.666``
    - Số thực -> ``4,03``
    - ``None`` / ``NaN`` -> ``"—"``
    """
    if value is None or pd.isna(value):
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)

    if abs(num) >= 1_000_000:
        compact = f"{num / 1_000_000:.{decimals}f}".replace(".", ",")
        return f"{prefix}{compact}M"
    if num.is_integer():
        formatted = f"{int(round(num)):,}".replace(",", ".")
        return f"{prefix}{formatted}"
    formatted = (
        f"{num:,.{decimals}f}"
        .replace(",", "_")
        .replace(".", ",")
        .replace("_", ".")
    )
    return f"{prefix}{formatted}"


def get_database_overview(db_path: str | Path | None = None) -> dict[str, Any]:
    """Truy vấn các chỉ số tổng quan nhẹ của CSDL DuckDB (read-only).

    Trả về dict rỗng nếu file DB chưa tồn tại hoặc không đọc được.
    """
    resolved = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    if not resolved.exists():
        return {}

    conn: duckdb.DuckDBPyConnection | None = None
    try:
        conn = duckdb.connect(str(resolved), read_only=True)
        fact_row = conn.execute(
            "SELECT COUNT(DISTINCT order_id), COUNT(*), ROUND(SUM(price), 2), "
            "ROUND(AVG(review_score), 2), COUNT(DISTINCT customer_key) "
            "FROM fact_orders"
        ).fetchone()
        date_row = conn.execute(
            "SELECT MIN(d.full_date), MAX(d.full_date) "
            "FROM fact_orders f JOIN dim_date d ON f.date_key = d.date_key"
        ).fetchone()
        tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
        table_counts = {
            t: int(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
            for t in tables
        }
    except Exception:  # noqa: BLE001
        return {}
    finally:
        if conn is not None:
            conn.close()

    def _fmt_month_year(val: Any) -> str:
        if val is None:
            return "—"
        return val.strftime("%m/%Y") if hasattr(val, "strftime") else str(val)

    orders, items, revenue, avg_review, customers = fact_row or (0, 0, 0.0, 0.0, 0)
    d_min, d_max = date_row or (None, None)
    return {
        "total_orders": int(orders or 0),
        "total_items": int(items or 0),
        "total_revenue": float(revenue or 0.0),
        "avg_review": float(avg_review or 0.0),
        "total_customers": int(customers or 0),
        "total_products": table_counts.get("dim_products", 0),
        "total_sellers": table_counts.get("dim_sellers", 0),
        "date_min": _fmt_month_year(d_min),
        "date_max": _fmt_month_year(d_max),
        "table_counts": table_counts,
    }


def get_table_preview(
    table_name: str,
    db_path: str | Path | None = None,
    limit: int = 10,
) -> pd.DataFrame:
    """Xem trước dữ liệu của một bảng hợp lệ trong Star Schema."""
    schema = get_schema_metadata()
    if table_name not in schema:
        raise ValueError(f"Bảng không hợp lệ: {table_name}")

    resolved = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    safe_limit = max(1, min(int(limit), 100))
    conn = duckdb.connect(str(resolved), read_only=True)
    try:
        return conn.execute(
            f'SELECT * FROM "{table_name}" LIMIT {safe_limit}'
        ).fetchdf()
    finally:
        conn.close()


def get_schema_summary() -> list[dict[str, Any]]:
    """Tổng hợp metadata Star Schema (fact_orders đứng đầu, tiếp đến các dim_*)."""
    schema = get_schema_metadata()
    relationships = get_table_relationships()
    summaries: list[dict[str, Any]] = []

    ordered_names = sorted(
        schema.keys(),
        key=lambda n: (0 if n.startswith("fact_") else 1, n),
    )
    for name in ordered_names:
        info = schema[name]
        columns_meta = info.get("columns", {})
        col_rows: list[dict[str, str]] = []
        for col_name, col_info in columns_meta.items():
            if col_info.get("references"):
                key_label = f"FK → {col_info['references']}"
            elif col_info.get("is_key"):
                key_label = "PK / Key"
            else:
                key_label = "—"
            col_rows.append({
                "Tên cột": col_name,
                "Kiểu dữ liệu": col_info.get("type", ""),
                "Khóa / Tham chiếu": key_label,
                "Mô tả": col_info.get("description", ""),
            })

        rel_rows = [
            r for r in relationships
            if r.get("from_table") == name or r.get("to_table") == name
        ]
        summaries.append({
            "name": name,
            "kind": "FACT" if name.startswith("fact_") else "DIMENSION",
            "description": info.get("description", ""),
            "grain": info.get("grain", ""),
            "column_count": len(col_rows),
            "columns": col_rows,
            "relationships": rel_rows,
        })
    return summaries


def make_history_entry(result: QueryResult | Any) -> dict[str, Any]:
    """Tạo bản ghi lịch sử từ ``QueryResult`` để lưu trong ``session_state`` và SQLite."""
    chart_spec = getattr(result, "chart_spec", None)
    chart_type = None
    if chart_spec is not None and getattr(chart_spec, "chart_type", None) is not None:
        chart_type = chart_spec.chart_type.value
    exec_ms = getattr(result, "execution_time_ms", 0.0) or 0.0
    now = datetime.now()
    return {
        "question": getattr(result, "question", ""),
        "success": bool(getattr(result, "success", False)),
        "chart_type": chart_type,
        "total_s": round(float(exec_ms) / 1000, 2),
        "timestamp": now.strftime("%H:%M:%S"),
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "result": result,
    }


def compute_history_metrics(history: list[dict[str, Any]]) -> dict[str, int]:
    """Tổng hợp số liệu thực thi & Self-Correction từ danh sách lịch sử đã lưu."""
    total_queries = len(history)
    first_try_success = 0
    corrected_success = 0
    blocked_security = 0
    for entry in history:
        res = entry.get("result")
        success = bool(entry.get("success", getattr(res, "success", False)))
        attempts = int(getattr(res, "correction_attempts", 0) or 0)
        err_type = getattr(res, "error_type", None)
        if err_type == "security":
            blocked_security += 1
        if success and attempts == 0:
            first_try_success += 1
        elif success:
            corrected_success += 1
    return {
        "total_queries": total_queries,
        "first_try_success": first_try_success,
        "corrected_success": corrected_success,
        "blocked_security": blocked_security,
    }


def build_session_log_df(history: list[dict[str, Any]]) -> pd.DataFrame:
    """Chuyển lịch sử phiên làm việc thành DataFrame phục vụ bảng & biểu đồ hiệu năng."""
    if not history:
        return pd.DataFrame(columns=_LOG_COLUMNS)

    rows = []
    for entry in history:
        res = entry.get("result")
        ct = entry.get("chart_type")
        _, ct_label = CHART_TYPE_LABELS.get(ct or "", ("", ct or "—"))
        rows.append({
            "Thời gian": entry.get("timestamp", ""),
            "Câu hỏi": entry.get("question", ""),
            "Trạng thái": "Thành công" if entry.get("success") else "Thất bại",
            "Biểu đồ": ct_label if ct else "—",
            "Tự sửa": int(getattr(res, "correction_attempts", 0) or 0),
            "Tổng (s)": float(entry.get("total_s", 0.0) or 0.0),
        })
    return pd.DataFrame(rows, columns=_LOG_COLUMNS)


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Xuất DataFrame thành CSV có BOM UTF-8 để Excel mở không lỗi dấu tiếng Việt."""
    return df.to_csv(index=False).encode("utf-8-sig")


def figure_to_html_bytes(fig: Any) -> bytes:
    """Xuất biểu đồ Plotly thành HTML độc lập (dùng Plotly.js từ CDN)."""
    return fig.to_html(include_plotlyjs="cdn").encode("utf-8")
