"""Sinh biểu đồ Plotly từ kết quả truy vấn, theo theme thống nhất.

Hàm chính: ``auto_generate_chart(df, sql, question)`` -> (Figure, ChartSpec).
"""

from __future__ import annotations

import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.visualization.chart_classifier import (
    ROLE_TEMPORAL,
    ChartSpec,
    ChartType,
    classify_chart_type,
)

logger = logging.getLogger(__name__)

# ===========================================================================
# Theme thống nhất
# ===========================================================================

COLOR_PALETTE: list[str] = [
    "#2563EB", "#F97316", "#10B981", "#EF4444", "#8B5CF6",
    "#14B8A6", "#F59E0B", "#EC4899", "#64748B", "#84CC16",
    "#0EA5E9", "#A855F7",
]
PRIMARY_COLOR = COLOR_PALETTE[0]
FONT_FAMILY = "Inter, Segoe UI, Arial, sans-serif"
MAX_BAR_CATEGORIES = 25
MAX_TABLE_ROWS = 50


def apply_theme(fig: go.Figure, title: str | None = None) -> go.Figure:
    """Áp dụng style chung (font, màu, lưới, lề) cho mọi biểu đồ."""
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title={"text": title or "", "x": 0.01, "xanchor": "left",
               "font": {"size": 18, "color": "#0F172A"}},
        font={"family": FONT_FAMILY, "size": 13, "color": "#334155"},
        colorway=COLOR_PALETTE,
        margin={"l": 60, "r": 30, "t": 60 if title else 30, "b": 60},
        hoverlabel={
            "bgcolor": "#0F172A",
            "bordercolor": "#0F172A",
            "font": {"family": FONT_FAMILY, "size": 12, "color": "#F8FAFC"},
        },
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        separators=",.",
    )
    fig.update_xaxes(showgrid=False, linecolor="#CBD5E1", title_font={"size": 13})
    fig.update_yaxes(gridcolor="#EDF2F7", zeroline=False, title_font={"size": 13})
    return fig


def _label(col: str | None) -> str:
    """Nhãn trục dễ đọc từ tên cột: total_revenue -> Total Revenue."""
    return "" if col is None else str(col).replace("_", " ").strip().title()


# ===========================================================================
# Các loại biểu đồ
# ===========================================================================

def create_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str = "",
                     hover: list[str] | None = None) -> go.Figure:
    """Bar chart; tự chuyển sang thanh ngang khi nhãn dài hoặc nhiều nhóm."""
    data = df.copy()
    if len(data) > MAX_BAR_CATEGORIES:
        data = data.nlargest(MAX_BAR_CATEGORIES, y_col)
        title = f"{title} (top {MAX_BAR_CATEGORIES})" if title else f"Top {MAX_BAR_CATEGORIES}"
    data[x_col] = data[x_col].astype(str)
    horizontal = len(data) > 8 or data[x_col].str.len().max() > 12
    if horizontal:
        data = data.sort_values(y_col, ascending=True)
        fig = px.bar(data, x=y_col, y=x_col, orientation="h", hover_data=hover or None,
                     color_discrete_sequence=[PRIMARY_COLOR],
                     labels={x_col: _label(x_col), y_col: _label(y_col)})
        fig.update_layout(height=max(380, 28 * len(data) + 120))
    else:
        fig = px.bar(data, x=x_col, y=y_col, hover_data=hover or None,
                     color_discrete_sequence=[PRIMARY_COLOR],
                     labels={x_col: _label(x_col), y_col: _label(y_col)})
    return apply_theme(fig, title)


def create_line_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str = "",
                      color_col: str | None = None, hover: list[str] | None = None) -> go.Figure:
    """Line chart cho chuỗi thời gian (có thể nhiều đường theo ``color_col``)."""
    data = df.sort_values([c for c in (color_col, x_col) if c])
    if color_col:
        data = data.assign(**{color_col: data[color_col].astype(str)})
    fig = px.line(data, x=x_col, y=y_col, color=color_col, markers=len(data) <= 60,
                  hover_data=hover or None,
                  labels={x_col: _label(x_col), y_col: _label(y_col),
                          **({color_col: _label(color_col)} if color_col else {})})
    return apply_theme(fig, title)


def create_pie_chart(df: pd.DataFrame, names_col: str, values_col: str,
                     title: str = "") -> go.Figure:
    """Pie (donut) chart cho câu hỏi về tỉ lệ / cơ cấu."""
    fig = px.pie(df, names=names_col, values=values_col, hole=0.4,
                 labels={names_col: _label(names_col), values_col: _label(values_col)})
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return apply_theme(fig, title)


def create_scatter_plot(df: pd.DataFrame, x_col: str, y_col: str, title: str = "",
                        hover: list[str] | None = None) -> go.Figure:
    """Scatter plot cho quan hệ giữa 2 biến số."""
    fig = px.scatter(df, x=x_col, y=y_col, hover_data=hover or None, opacity=0.7,
                     color_discrete_sequence=[PRIMARY_COLOR],
                     labels={x_col: _label(x_col), y_col: _label(y_col)})
    return apply_theme(fig, title)


def create_histogram(df: pd.DataFrame, col: str, title: str = "") -> go.Figure:
    """Histogram cho phân phối của 1 biến số."""
    fig = px.histogram(df, x=col, nbins=min(50, max(10, len(df) // 5)),
                       color_discrete_sequence=[PRIMARY_COLOR],
                       labels={col: _label(col)})
    fig.update_layout(bargap=0.05, yaxis_title="Số lượng")
    return apply_theme(fig, title)


def create_grouped_bar(df: pd.DataFrame, x_col: str, y_col: str, color_col: str,
                       title: str = "", hover: list[str] | None = None) -> go.Figure:
    """Grouped bar: so sánh ``y_col`` theo 2 chiều phân loại."""
    data = df.assign(**{x_col: df[x_col].astype(str), color_col: df[color_col].astype(str)})
    fig = px.bar(data, x=x_col, y=y_col, color=color_col, barmode="group",
                 hover_data=hover or None,
                 labels={x_col: _label(x_col), y_col: _label(y_col), color_col: _label(color_col)})
    return apply_theme(fig, title)


def create_map(df: pd.DataFrame, lat_col: str, lon_col: str, size_col: str | None = None,
               label_col: str | None = None, title: str = "",
               hover: list[str] | None = None) -> go.Figure:
    """Bản đồ điểm (MapLibre, không cần token)."""
    data = df.dropna(subset=[lat_col, lon_col])
    kwargs = dict(lat=lat_col, lon=lon_col, hover_name=label_col,
                  hover_data=hover or None, zoom=3, height=520,
                  color_discrete_sequence=[PRIMARY_COLOR])
    if size_col and (data[size_col] >= 0).all():
        kwargs["size"] = size_col
    try:
        fig = px.scatter_map(data, **kwargs)
        fig.update_layout(map_style="carto-positron")
    except AttributeError:  # plotly cũ
        fig = px.scatter_mapbox(data, **kwargs)
        fig.update_layout(mapbox_style="carto-positron")
    return apply_theme(fig, title)


def create_kpi(df: pd.DataFrame, value_col: str, title: str = "",
               extra_cols: list[str] | None = None) -> go.Figure:
    """Thẻ chỉ số cho kết quả 1 dòng (tối đa 4 chỉ số)."""
    cols = [value_col, *(extra_cols or [])][:4]
    fig = go.Figure()
    for i, col in enumerate(cols):
        value = df[col].iloc[0]
        fig.add_trace(go.Indicator(
            mode="number",
            value=float(value) if pd.notna(value) else 0.0,
            title={"text": _label(col), "font": {"size": 15}},
            number={"valueformat": ",.2f" if not float(value).is_integer() else ",.0f",
                    "font": {"color": COLOR_PALETTE[i]}},
            domain={"row": 0, "column": i},
        ))
    fig.update_layout(grid={"rows": 1, "columns": len(cols), "pattern": "independent"}, height=220)
    return apply_theme(fig, title)


def create_table(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Bảng dữ liệu (tối đa 50 dòng)."""
    data = df.head(MAX_TABLE_ROWS)
    fig = go.Figure(go.Table(
        header={"values": [_label(c) for c in data.columns], "fill_color": PRIMARY_COLOR,
                "font": {"color": "white", "size": 13}, "align": "left"},
        cells={"values": [data[c].astype(str).tolist() for c in data.columns],
               "fill_color": [["#F8FAFC", "#FFFFFF"] * (len(data) // 2 + 1)],
               "align": "left"},
    ))
    fig.update_layout(height=min(600, 40 + 28 * (len(data) + 1)))
    return apply_theme(fig, title)


# ===========================================================================
# Hàm tổng hợp
# ===========================================================================

def build_chart(df: pd.DataFrame, spec: ChartSpec, title: str = "") -> go.Figure:
    """Tạo Figure theo ChartSpec đã chọn."""
    ct = spec.chart_type
    if ct == ChartType.BAR:
        return create_bar_chart(df, spec.x, spec.y, title, spec.hover)
    if ct == ChartType.LINE:
        data = df
        # Cột thời gian dạng số (month 1..12): giữ trục rời rạc theo thứ tự
        if spec.roles.get(spec.x) == ROLE_TEMPORAL:
            data = df.copy()
        fig = create_line_chart(data, spec.x, spec.y, title, spec.color, spec.hover)
        if spec.roles.get(spec.x) == ROLE_TEMPORAL:
            fig.update_xaxes(dtick=1)
        return fig
    if ct == ChartType.PIE:
        return create_pie_chart(df, spec.x, spec.y, title)
    if ct == ChartType.SCATTER:
        return create_scatter_plot(df, spec.x, spec.y, title, spec.hover)
    if ct == ChartType.HISTOGRAM:
        return create_histogram(df, spec.x, title)
    if ct == ChartType.GROUPED_BAR:
        return create_grouped_bar(df, spec.x, spec.y, spec.color, title, spec.hover)
    if ct == ChartType.MAP:
        return create_map(df, spec.lat, spec.lon, spec.y, spec.x, title, spec.hover)
    if ct == ChartType.KPI:
        return create_kpi(df, spec.y, title, spec.hover)
    return create_table(df, title)


def auto_generate_chart(
    df: pd.DataFrame,
    sql: str = "",
    question: str = "",
    title: str | None = None,
) -> tuple[go.Figure | None, ChartSpec]:
    """Tự động chọn và vẽ biểu đồ cho kết quả truy vấn.

    Args:
        df: DataFrame kết quả.
        sql: SQL đã chạy.
        question: Câu hỏi gốc (dùng làm tiêu đề mặc định).
        title: Tiêu đề tùy chọn.

    Returns:
        (Figure hoặc None nếu không có dữ liệu, ChartSpec).
    """
    spec = classify_chart_type(df, sql=sql, question=question)
    if df is None or df.empty:
        return None, spec
    chart_title = title if title is not None else question
    try:
        fig = build_chart(df, spec, chart_title)
    except Exception as e:  # Vẽ lỗi -> hiển thị bảng thay vì làm hỏng pipeline
        logger.warning("Vẽ %s thất bại (%s); chuyển sang bảng.", spec.chart_type.value, e)
        spec = ChartSpec(ChartType.TABLE, reason=f"Vẽ biểu đồ lỗi: {e}", roles=spec.roles)
        fig = create_table(df, chart_title)
    logger.info("Biểu đồ: %s - %s", spec.chart_type.value, spec.reason)
    return fig, spec
