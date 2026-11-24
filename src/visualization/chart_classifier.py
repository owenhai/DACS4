"""Phân loại biểu đồ tự động dựa trên đặc điểm DataFrame kết quả.

Thuật toán dựa trên luật (rule-based), không gọi LLM:
- Nhanh, xác định (cùng dữ liệu -> cùng biểu đồ), không tốn API.
- Dễ giải thích: mỗi quyết định kèm ``reason``.

Bảng luật (theo thứ tự ưu tiên):

=============================================  ==================
Đặc điểm dữ liệu                               Biểu đồ
=============================================  ==================
0 dòng / không có cột số                       TABLE
Có cột latitude + longitude                    MAP
1 dòng, có cột số                              KPI (thẻ chỉ số)
Cột thời gian + cột số                         LINE
2 cột phân loại + 1 cột số                     GROUPED_BAR
1 cột phân loại + cột số, câu hỏi về tỉ lệ      PIE (≤ 8 nhóm)
1 cột phân loại + cột số                       BAR
2+ cột số (không có phân loại)                 SCATTER
1 cột số, nhiều dòng                           HISTOGRAM
Còn lại                                        TABLE
=============================================  ==================

Ghi chú: đề cương ban đầu đề xuất "≤ 10 dòng → Table", nhưng các câu hỏi
"Top 5/Top 10" là trường hợp phổ biến nhất và hiển thị tốt hơn bằng Bar
chart, nên luật Table chỉ áp dụng khi dữ liệu không vẽ được.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
from pandas.api import types as ptypes


class ChartType(str, Enum):
    """Các loại biểu đồ hỗ trợ."""

    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    GROUPED_BAR = "grouped_bar"
    MAP = "map"
    KPI = "kpi"
    TABLE = "table"


# Vai trò của cột
ROLE_NUMERIC = "numeric"
ROLE_CATEGORICAL = "categorical"
ROLE_DATETIME = "datetime"
ROLE_TEMPORAL = "temporal"  # số nguyên biểu diễn thời gian: year, month, quarter...
ROLE_LATITUDE = "latitude"
ROLE_LONGITUDE = "longitude"
ROLE_IDENTIFIER = "identifier"  # khóa/ID - không dùng làm trục số

MAX_PIE_SLICES = 8
MAX_COLOR_GROUPS = 12

_PROPORTION_WORDS = (
    "tỉ lệ", "tỷ lệ", "phần trăm", "cơ cấu", "tỉ trọng", "tỷ trọng", "chiếm",
    "percent", "percentage", "proportion", "share", "ratio", "distribution of",
)
_PROPORTION_COL_HINTS = ("pct", "percent", "percentage", "share", "ratio", "ti_le", "proportion")
_TEMPORAL_NAMES = {
    "year": (1990, 2100), "nam": (1990, 2100),
    "month": (1, 12), "thang": (1, 12),
    "quarter": (1, 4), "quy": (1, 4),
    "week": (1, 53), "day": (1, 31), "day_of_week": (0, 7), "hour": (0, 23),
}
_YEAR_MONTH_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


@dataclass
class ChartSpec:
    """Mô tả biểu đồ được chọn.

    Attributes:
        chart_type: Loại biểu đồ.
        x: Cột trục X (hoặc cột nhãn cho Pie, cột giá trị cho Histogram).
        y: Cột giá trị chính (trục Y / giá trị Pie).
        color: Cột phân nhóm màu (Grouped bar, Line nhiều đường).
        hover: Các cột bổ sung hiển thị khi rê chuột.
        lat, lon: Cột tọa độ cho Map.
        reason: Giải thích vì sao chọn biểu đồ này.
        roles: Vai trò đã phát hiện cho từng cột.
    """

    chart_type: ChartType
    x: str | None = None
    y: str | None = None
    color: str | None = None
    hover: list[str] = field(default_factory=list)
    lat: str | None = None
    lon: str | None = None
    reason: str = ""
    roles: dict[str, str] = field(default_factory=dict)


# ===========================================================================
# Phát hiện vai trò cột
# ===========================================================================

def detect_column_roles(df: pd.DataFrame) -> dict[str, str]:
    """Xác định vai trò của từng cột: numeric, categorical, datetime, temporal,
    latitude, longitude, identifier.

    Args:
        df: DataFrame kết quả truy vấn.

    Returns:
        Dict ``{tên_cột: vai_trò}`` theo thứ tự cột.
    """
    roles: dict[str, str] = {}
    for col in df.columns:
        roles[col] = _detect_role(df[col], str(col))
    return roles


def _detect_role(series: pd.Series, name: str) -> str:
    lname = name.lower()
    non_null = series.dropna()

    # Datetime thật
    if ptypes.is_datetime64_any_dtype(series):
        return ROLE_DATETIME
    if ptypes.is_bool_dtype(series):
        return ROLE_CATEGORICAL

    if ptypes.is_numeric_dtype(series):
        # Tọa độ
        if _is_coord_name(lname, ("lat", "latitude")) and _in_range(non_null, -90, 90):
            return ROLE_LATITUDE
        if _is_coord_name(lname, ("lng", "lon", "long", "longitude")) and _in_range(non_null, -180, 180):
            return ROLE_LONGITUDE
        # Khóa / ID
        if lname.endswith(("_key", "_id", "_prefix")) or lname in ("id", "key", "zip_code"):
            return ROLE_IDENTIFIER
        # Số nguyên biểu diễn thời gian (year, month, ...)
        base = lname.split("_")[-1] if lname not in _TEMPORAL_NAMES else lname
        for tname in (lname, base):
            if tname in _TEMPORAL_NAMES and ptypes.is_integer_dtype(series) or (
                tname in _TEMPORAL_NAMES and _is_whole(non_null)
            ):
                lo, hi = _TEMPORAL_NAMES[tname]
                if _in_range(non_null, lo, hi):
                    return ROLE_TEMPORAL
        return ROLE_NUMERIC

    # Object / string
    if len(non_null) and non_null.map(type).isin([pd.Timestamp]).all():
        return ROLE_DATETIME
    if len(non_null):
        sample = non_null.astype(str).head(20)
        if _date_like_values(non_null):
            return ROLE_DATETIME
        if sample.str.match(_YEAR_MONTH_RE).all():
            return ROLE_DATETIME
    return ROLE_CATEGORICAL


def _date_like_values(values: pd.Series) -> bool:
    import datetime as _dt
    head = values.head(20)
    return bool(len(head)) and head.map(lambda v: isinstance(v, (_dt.date, _dt.datetime))).all()


def _is_coord_name(lname: str, keys: tuple[str, ...]) -> bool:
    parts = re.split(r"[_\W]+", lname)
    return any(k in parts for k in keys)


def _in_range(values: pd.Series, lo: float, hi: float) -> bool:
    if values.empty:
        return False
    try:
        return bool(values.min() >= lo and values.max() <= hi)
    except TypeError:
        return False


def _is_whole(values: pd.Series) -> bool:
    try:
        return bool(len(values)) and bool((values % 1 == 0).all())
    except TypeError:
        return False


# ===========================================================================
# Phân loại biểu đồ
# ===========================================================================

def classify_chart_type(
    df: pd.DataFrame,
    sql: str = "",
    question: str = "",
) -> ChartSpec:
    """Chọn loại biểu đồ phù hợp cho kết quả truy vấn.

    Args:
        df: DataFrame kết quả.
        sql: Câu SQL (dùng để nhận biết ORDER BY / tỉ lệ).
        question: Câu hỏi gốc (dùng để nhận biết câu hỏi về tỉ lệ).

    Returns:
        ChartSpec mô tả biểu đồ và lý do chọn.
    """
    if df is None or df.empty:
        return ChartSpec(ChartType.TABLE, reason="Không có dữ liệu để vẽ.")

    roles = detect_column_roles(df)
    by_role: dict[str, list[str]] = {}
    for col, role in roles.items():
        by_role.setdefault(role, []).append(col)

    numeric = by_role.get(ROLE_NUMERIC, [])
    categorical = by_role.get(ROLE_CATEGORICAL, [])
    datetimes = by_role.get(ROLE_DATETIME, []) + by_role.get(ROLE_TEMPORAL, [])
    lat = (by_role.get(ROLE_LATITUDE) or [None])[0]
    lon = (by_role.get(ROLE_LONGITUDE) or [None])[0]

    def spec(chart_type: ChartType, reason: str, **kw) -> ChartSpec:
        return ChartSpec(chart_type, reason=reason, roles=roles, **kw)

    # Nếu chỉ có cột thời gian dạng số mà không có cột số khác,
    # cột temporal có thể là giá trị (ví dụ: "năm có doanh thu cao nhất")
    if not numeric and by_role.get(ROLE_TEMPORAL) and len(df.columns) == 1:
        numeric = by_role[ROLE_TEMPORAL]
        datetimes = by_role.get(ROLE_DATETIME, [])

    # 1. Bản đồ
    if lat and lon:
        size = numeric[0] if numeric else None
        label = (categorical or [None])[0]
        return spec(
            ChartType.MAP, "Dữ liệu có cột vĩ độ/kinh độ.",
            lat=lat, lon=lon, y=size, x=label,
            hover=[c for c in df.columns if c not in (lat, lon)][:5],
        )

    if not numeric:
        return spec(ChartType.TABLE, "Không có cột số để vẽ biểu đồ.")

    # 2. Một dòng -> thẻ KPI
    if len(df) == 1:
        return spec(ChartType.KPI, "Kết quả chỉ có 1 dòng - hiển thị dạng thẻ chỉ số.",
                    y=numeric[0], hover=numeric[1:])

    primary = _primary_metric(numeric, question)
    others = [c for c in numeric if c != primary]

    # 3. Chuỗi thời gian
    if datetimes:
        time_col = _best_time_column(datetimes, roles)
        color = None
        # Chỉ tách nhiều đường khi mỗi mốc thời gian có nhiều dòng; nếu không,
        # cột phân loại chỉ là nhãn của thời gian (ví dụ month_name) -> hover
        if df[time_col].duplicated().any():
            cat_candidates = [c for c in categorical if 1 < df[c].nunique() <= MAX_COLOR_GROUPS]
            outer = [c for c in datetimes if c != time_col and roles[c] == ROLE_TEMPORAL]
            if cat_candidates:
                color = cat_candidates[0]
            elif outer and df[outer[0]].nunique() <= MAX_COLOR_GROUPS:
                # Ví dụ: (year, month, revenue) -> mỗi năm 1 đường, trục X là tháng
                color = outer[0]
        labels = [c for c in categorical + datetimes if c not in (time_col, color)]
        return spec(ChartType.LINE, f"Cột thời gian '{time_col}' + cột số '{primary}'.",
                    x=time_col, y=primary, color=color, hover=labels + others)

    # 4. Hai cột phân loại -> grouped bar
    if len(categorical) >= 2:
        x_col, color_col = _order_categoricals(df, categorical[:2])
        if df[color_col].nunique() <= MAX_COLOR_GROUPS:
            return spec(ChartType.GROUPED_BAR,
                        f"2 cột phân loại ('{x_col}', '{color_col}') + cột số '{primary}'.",
                        x=x_col, y=primary, color=color_col, hover=others)

    # 5. Một cột phân loại
    if categorical:
        cat = categorical[0]
        n_groups = df[cat].nunique()
        if (
            _asks_for_proportion(question, sql, primary)
            and n_groups <= MAX_PIE_SLICES
            and (df[primary].dropna() >= 0).all()
        ):
            return spec(ChartType.PIE, f"Câu hỏi về tỉ lệ, {n_groups} nhóm của '{cat}'.",
                        x=cat, y=primary, hover=others)
        return spec(ChartType.BAR, f"So sánh '{primary}' giữa các nhóm '{cat}'.",
                    x=cat, y=primary, hover=others + categorical[1:])

    # 6. Chỉ có cột số
    if len(numeric) >= 2:
        return spec(ChartType.SCATTER, f"Quan hệ giữa '{numeric[0]}' và '{numeric[1]}'.",
                    x=numeric[0], y=numeric[1], hover=numeric[2:])
    if len(df) >= 5:
        return spec(ChartType.HISTOGRAM, f"Phân phối của '{numeric[0]}'.", x=numeric[0])

    return spec(ChartType.TABLE, "Dữ liệu ít, hiển thị dạng bảng.")


# ===========================================================================
# Helpers
# ===========================================================================

def _primary_metric(numeric: list[str], question: str) -> str:
    """Chọn cột số chính: ưu tiên cột có tên xuất hiện trong câu hỏi
    hoặc cột tỉ lệ khi hỏi về tỉ lệ; mặc định cột số đầu tiên."""
    q = (question or "").lower()
    if any(w in q for w in _PROPORTION_WORDS):
        for col in numeric:
            if any(h in col.lower() for h in _PROPORTION_COL_HINTS):
                return col
    for col in numeric:
        words = [w for w in re.split(r"[_\W]+", col.lower()) if len(w) > 3]
        if any(w in q for w in words):
            return col
    return numeric[0]


def _best_time_column(datetimes: list[str], roles: dict[str, str]) -> str:
    """Ưu tiên datetime thật; trong các cột temporal ưu tiên cột chi tiết nhất."""
    real = [c for c in datetimes if roles[c] == ROLE_DATETIME]
    if real:
        return real[0]
    granularity = ["day", "week", "month", "thang", "quarter", "quy", "year", "nam"]
    def rank(col: str) -> int:
        lc = col.lower()
        for i, g in enumerate(granularity):
            if lc == g or lc.endswith("_" + g):
                return i
        return len(granularity)
    return sorted(datetimes, key=rank)[0]


def _order_categoricals(df: pd.DataFrame, cats: list[str]) -> tuple[str, str]:
    """Cột có nhiều giá trị hơn làm trục X, cột ít giá trị làm màu."""
    a, b = cats
    return (a, b) if df[a].nunique() >= df[b].nunique() else (b, a)


def _asks_for_proportion(question: str, sql: str, metric: str) -> bool:
    text = f"{question or ''} {metric}".lower()
    if any(w in text for w in _PROPORTION_WORDS):
        return True
    if any(h in metric.lower() for h in _PROPORTION_COL_HINTS):
        return True
    return "over ()" in (sql or "").lower() and "100" in (sql or "")
