"""Unit tests Tuần 4: phân loại biểu đồ, sinh biểu đồ Plotly, Insight Generation
và tích hợp vào pipeline. Chạy offline (LLM giả lập)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from src.models.insight_generator import (
    InsightResult,
    compute_statistics,
    fmt_number,
    format_statistics,
    generate_insights,
    parse_bullets,
    rule_based_insights,
)
from src.models.prompt_templates import build_insight_prompt
from src.models.text_to_sql import TextToSQLPipeline
from src.visualization.chart_classifier import (
    ROLE_CATEGORICAL,
    ROLE_DATETIME,
    ROLE_IDENTIFIER,
    ROLE_LATITUDE,
    ROLE_LONGITUDE,
    ROLE_NUMERIC,
    ROLE_TEMPORAL,
    ChartType,
    classify_chart_type,
    detect_column_roles,
)
from src.visualization.chart_generator import (
    COLOR_PALETTE,
    auto_generate_chart,
    create_bar_chart,
    create_grouped_bar,
    create_histogram,
    create_line_chart,
    create_pie_chart,
    create_scatter_plot,
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "database" / "olist_analytics.duckdb"
requires_db = pytest.mark.skipif(not DB_PATH.exists(), reason="DuckDB database chưa được tạo")


# ===========================================================================
# Dữ liệu mẫu
# ===========================================================================

@pytest.fixture
def df_category():
    return pd.DataFrame({"category": ["bed_bath", "health", "sports", "toys", "auto"],
                         "revenue": [1_000_000.5, 900_000.0, 800_000.0, 300_000.0, 100_000.0]})


@pytest.fixture
def df_monthly():
    return pd.DataFrame({"month": list(range(1, 13)),
                         "month_name": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                         "revenue": [100, 120, 130, 150, 170, 160, 180, 200, 210, 230, 400, 250]})


# ===========================================================================
# 4.1 detect_column_roles
# ===========================================================================

def test_roles_basic():
    df = pd.DataFrame({
        "full_date": pd.to_datetime(["2018-01-01", "2018-01-02"]),
        "year": [2017, 2018],
        "month": [1, 2],
        "customer_state": ["SP", "RJ"],
        "price": [10.5, 20.0],
        "customer_key": [1, 2],
        "geolocation_lat": [-23.5, -22.9],
        "geolocation_lng": [-46.6, -43.2],
        "is_weekend": [True, False],
    })
    roles = detect_column_roles(df)
    assert roles == {
        "full_date": ROLE_DATETIME, "year": ROLE_TEMPORAL, "month": ROLE_TEMPORAL,
        "customer_state": ROLE_CATEGORICAL, "price": ROLE_NUMERIC,
        "customer_key": ROLE_IDENTIFIER, "geolocation_lat": ROLE_LATITUDE,
        "geolocation_lng": ROLE_LONGITUDE, "is_weekend": ROLE_CATEGORICAL,
    }


def test_roles_date_objects_and_year_month_strings():
    import datetime as dt
    df = pd.DataFrame({"d": [dt.date(2018, 1, 1), dt.date(2018, 2, 1)],
                       "ym": ["2018-01", "2018-02"], "v": [1, 2]})
    roles = detect_column_roles(df)
    assert roles["d"] == ROLE_DATETIME and roles["ym"] == ROLE_DATETIME


def test_month_out_of_range_is_numeric():
    df = pd.DataFrame({"month": [1, 25, 40], "v": [1, 2, 3]})
    assert detect_column_roles(df)["month"] == ROLE_NUMERIC


# ===========================================================================
# 4.1 classify_chart_type
# ===========================================================================

def test_empty_is_table():
    assert classify_chart_type(pd.DataFrame()).chart_type == ChartType.TABLE


def test_single_row_is_kpi():
    df = pd.DataFrame({"total_orders": [99441], "revenue": [13_591_643.7]})
    spec = classify_chart_type(df)
    assert spec.chart_type == ChartType.KPI and spec.y == "total_orders"


def test_category_numeric_is_bar(df_category):
    spec = classify_chart_type(df_category, question="Top 5 danh mục doanh thu cao nhất?")
    assert (spec.chart_type, spec.x, spec.y) == (ChartType.BAR, "category", "revenue")
    assert spec.reason


def test_proportion_question_is_pie():
    df = pd.DataFrame({"payment_type": ["credit_card", "boleto", "voucher", "debit_card"],
                       "n": [76795, 19784, 5775, 1529]})
    spec = classify_chart_type(df, question="Tỉ lệ đơn hàng theo phương thức thanh toán?")
    assert spec.chart_type == ChartType.PIE


def test_pct_column_is_pie_without_keyword():
    df = pd.DataFrame({"status": ["delivered", "canceled"], "pct": [97.0, 3.0]})
    assert classify_chart_type(df).chart_type == ChartType.PIE


def test_too_many_slices_falls_back_to_bar():
    df = pd.DataFrame({"state": [f"S{i}" for i in range(20)], "share": range(1, 21)})
    assert classify_chart_type(df, question="tỉ lệ theo bang").chart_type == ChartType.BAR


def test_monthly_is_single_line_with_label_in_hover(df_monthly):
    spec = classify_chart_type(df_monthly)
    assert spec.chart_type == ChartType.LINE
    assert spec.x == "month" and spec.color is None
    assert "month_name" in spec.hover


def test_year_month_is_multi_line():
    df = pd.DataFrame({"year": [2017] * 12 + [2018] * 12,
                       "month": list(range(1, 13)) * 2, "revenue": range(24)})
    spec = classify_chart_type(df)
    assert spec.chart_type == ChartType.LINE and spec.x == "month" and spec.color == "year"


def test_datetime_series_is_line():
    df = pd.DataFrame({"full_date": pd.date_range("2018-01-01", periods=30), "revenue": range(30)})
    spec = classify_chart_type(df)
    assert spec.chart_type == ChartType.LINE and spec.x == "full_date"


def test_two_categoricals_is_grouped_bar():
    df = pd.DataFrame({"state": ["SP", "SP", "RJ", "RJ", "MG", "MG"],
                       "payment": ["card", "boleto"] * 3, "revenue": [5, 2, 4, 1, 3, 1]})
    spec = classify_chart_type(df)
    assert spec.chart_type == ChartType.GROUPED_BAR and spec.color is not None


def test_two_numeric_is_scatter():
    df = pd.DataFrame({"price": np.random.rand(50), "freight_value": np.random.rand(50)})
    assert classify_chart_type(df).chart_type == ChartType.SCATTER


def test_single_numeric_is_histogram():
    df = pd.DataFrame({"delivery_days": np.random.randint(1, 30, 200)})
    assert classify_chart_type(df).chart_type == ChartType.HISTOGRAM


def test_lat_lng_is_map():
    df = pd.DataFrame({"city": ["sao paulo", "rio"], "lat": [-23.5, -22.9], "lng": [-46.6, -43.2]})
    spec = classify_chart_type(df)
    assert spec.chart_type == ChartType.MAP and spec.lat == "lat" and spec.lon == "lng"


def test_no_numeric_is_table():
    df = pd.DataFrame({"order_id": ["a", "b"], "status": ["x", "y"]})
    assert classify_chart_type(df).chart_type == ChartType.TABLE


def test_primary_metric_matches_question():
    df = pd.DataFrame({"state": ["SP", "RJ", "MG"], "total_orders": [10, 8, 6],
                       "avg_review_score": [4.1, 3.9, 4.0]})
    spec = classify_chart_type(df, question="Điểm review trung bình theo bang?")
    assert spec.y == "avg_review_score"


# ===========================================================================
# 4.2 Chart generator
# ===========================================================================

def test_create_functions_return_figures(df_category, df_monthly):
    figs = [
        create_bar_chart(df_category, "category", "revenue", "t"),
        create_line_chart(df_monthly, "month", "revenue", "t"),
        create_pie_chart(df_category, "category", "revenue", "t"),
        create_scatter_plot(df_monthly, "month", "revenue", "t"),
        create_histogram(df_monthly, "revenue", "t"),
        create_grouped_bar(pd.DataFrame({"a": ["x", "x", "y"], "b": ["p", "q", "p"], "v": [1, 2, 3]}),
                           "a", "v", "b", "t"),
    ]
    for fig in figs:
        assert isinstance(fig, go.Figure) and len(fig.data) >= 1
        # Theme thống nhất
        assert fig.layout.font.family.startswith("Inter")
        assert list(fig.layout.colorway) == COLOR_PALETTE


def test_bar_chart_limits_categories():
    df = pd.DataFrame({"c": [f"cat{i}" for i in range(60)], "v": range(60)})
    fig = create_bar_chart(df, "c", "v", "t")
    assert len(fig.data[0].y) == 25  # horizontal -> labels on y


@pytest.mark.parametrize("df,question,trace_type", [
    (pd.DataFrame({"c": ["a", "b", "c"], "v": [3, 2, 1]}), "", "bar"),
    (pd.DataFrame({"payment_type": ["a", "b"], "n": [3, 1]}), "tỉ lệ thanh toán", "pie"),
    (pd.DataFrame({"full_date": pd.date_range("2018-01-01", periods=5), "v": range(5)}), "", "scatter"),
    (pd.DataFrame({"total": [5.0]}), "", "indicator"),
    (pd.DataFrame({"id": ["x", "y"], "s": ["a", "b"]}), "", "table"),
    (pd.DataFrame({"city": ["a", "b"], "lat": [-23.5, -22.9], "lng": [-46.6, -43.2]}), "", "scattermap"),
])
def test_auto_generate_chart_trace_types(df, question, trace_type):
    fig, spec = auto_generate_chart(df, "", question)
    assert fig.data[0].type == trace_type


def test_auto_generate_chart_empty():
    fig, spec = auto_generate_chart(pd.DataFrame({"a": []}), "", "q")
    assert fig is None and spec.chart_type == ChartType.TABLE


def test_auto_generate_chart_falls_back_to_table_on_error(monkeypatch):
    import src.visualization.chart_generator as cg
    monkeypatch.setattr(cg, "create_bar_chart", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    fig, spec = auto_generate_chart(pd.DataFrame({"c": ["a", "b"], "v": [1, 2]}))
    assert spec.chart_type == ChartType.TABLE and fig.data[0].type == "table"


# ===========================================================================
# 4.3 Statistics & insights
# ===========================================================================

def test_fmt_number_vietnamese():
    assert fmt_number(1234567.891) == "1.234.567,89"
    assert fmt_number(1000) == "1.000"
    assert fmt_number(None) == "N/A"


def test_group_statistics(df_category):
    stats = compute_statistics(df_category, question="Top danh mục")
    g = stats["groups"]
    assert g["top"]["label"] == "bed_bath" and g["bottom"]["label"] == "auto"
    assert g["top_share_pct"] == pytest.approx(1_000_000.5 / 3_100_000.5 * 100)
    assert g["top_vs_bottom_ratio"] == pytest.approx(10.000005)
    assert stats["metrics"]["revenue"]["sum"] == pytest.approx(3_100_000.5)


def test_trend_statistics(df_monthly):
    stats = compute_statistics(df_monthly)
    t = stats["trend"]
    assert t["direction"] == "tăng"
    assert t["peak"]["time"] == "11" and t["peak"]["value"] == 400
    assert t["change_pct"] == pytest.approx(150.0)
    assert "groups" not in stats


def test_decreasing_trend():
    df = pd.DataFrame({"year": [2016, 2017, 2018], "orders": [300, 200, 100]})
    assert compute_statistics(df)["trend"]["direction"] == "giảm"


def test_outlier_detection(df_monthly):
    stats = compute_statistics(df_monthly)
    o = stats["outliers"]
    assert o["high_count"] == 1 and o["high_labels"] == ["Nov"]


def test_format_statistics_contains_key_numbers(df_category):
    text = format_statistics(compute_statistics(df_category))
    assert "bed_bath" in text and "1.000.000,50" in text and "top 3" in text


def test_rule_based_insights(df_category, df_monthly):
    b = rule_based_insights(compute_statistics(df_category))
    assert 2 <= len(b) <= 5 and "bed_bath" in b[0]
    b2 = rule_based_insights(compute_statistics(df_monthly))
    assert any("tăng" in x for x in b2)
    assert rule_based_insights({"row_count": 0})[0].startswith("Truy vấn không trả về")


def test_parse_bullets():
    raw = "Nhận xét:\n- **SP** dẫn đầu.\n* RJ thứ hai.\n1. MG thứ ba.\n\n• AC thấp nhất."
    assert parse_bullets(raw) == ["SP dẫn đầu.", "RJ thứ hai.", "MG thứ ba.", "AC thấp nhất."]


def test_insight_prompt_contains_statistics():
    p = build_insight_prompt("q?", "SELECT 1", "preview", 3, statistics_text="- tổng=10")
    assert "Pre-computed statistics" in p and "tổng=10" in p and "Vietnamese" in p
    # Tương thích ngược: không truyền statistics_text
    assert "Pre-computed" not in build_insight_prompt("q?", "SELECT 1", "preview", 3)


class RecordingLLM:
    def __init__(self, response: str | Exception):
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str, **_kw) -> str:
        self.prompts.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_generate_insights_with_llm(df_category):
    llm = RecordingLLM("- bed_bath dẫn đầu.\n- auto thấp nhất.\n- Top 3 chiếm phần lớn.")
    result = generate_insights("Top danh mục?", "SELECT ...", df_category, llm_client=llm)
    assert isinstance(result, InsightResult)
    assert result.source == "llm" and len(result.bullets) == 3
    assert "Pre-computed statistics" in llm.prompts[0] and "bed_bath" in llm.prompts[0]
    assert result.text.startswith("- bed_bath")


def test_generate_insights_falls_back_on_llm_error(df_category):
    result = generate_insights("q", "sql", df_category, llm_client=RecordingLLM(RuntimeError("503")))
    assert result.source == "rule" and result.bullets and "503" in result.error


def test_generate_insights_empty_llm_response(df_category):
    result = generate_insights("q", "sql", df_category, llm_client=RecordingLLM("  \n "))
    assert result.source == "rule"


def test_generate_insights_without_llm(df_category):
    assert generate_insights("q", "sql", df_category).source == "rule"


# ===========================================================================
# 4.4 Tích hợp pipeline (10 câu hỏi, LLM giả lập + DuckDB thật)
# ===========================================================================

class ScriptedLLM:
    """Trả SQL cho prompt Text-to-SQL, trả bullet cho prompt insight."""

    def __init__(self, sql_by_question: dict[str, str], insight_error: bool = False):
        self.sql_by_question = sql_by_question
        self.insight_error = insight_error
        self.insight_calls = 0

    def generate(self, prompt: str, **_kw) -> str:
        if "Pre-computed statistics" in prompt or "Insights (Vietnamese" in prompt:
            self.insight_calls += 1
            if self.insight_error:
                raise RuntimeError("503 UNAVAILABLE")
            return "- Nhận xét 1.\n- Nhận xét 2.\n- Nhận xét 3."
        for q, sql in self.sql_by_question.items():
            if q in prompt:
                return sql
        raise RuntimeError("no script")


E2E = [
    ("Tổng số đơn hàng?", "SELECT COUNT(DISTINCT order_id) AS total_orders FROM fact_orders", ChartType.KPI),
    ("Top 5 danh mục doanh thu?",
     "SELECT p.product_category_name_english AS category, ROUND(SUM(f.price),2) AS revenue "
     "FROM fact_orders f JOIN dim_products p ON f.product_key=p.product_key "
     "GROUP BY 1 ORDER BY 2 DESC LIMIT 5", ChartType.BAR),
    ("Doanh thu theo tháng năm 2017?",
     "SELECT d.month, d.month_name, ROUND(SUM(f.price),2) AS revenue FROM fact_orders f "
     "JOIN dim_date d ON f.date_key=d.date_key WHERE d.year=2017 GROUP BY 1,2 ORDER BY 1", ChartType.LINE),
    ("Doanh thu theo tháng của từng năm?",
     "SELECT d.year, d.month, SUM(f.price) AS revenue FROM fact_orders f "
     "JOIN dim_date d ON f.date_key=d.date_key GROUP BY 1,2", ChartType.LINE),
    ("Tỉ lệ đơn theo phương thức thanh toán?",
     "SELECT payment_type, COUNT(DISTINCT order_id) AS orders FROM fact_orders GROUP BY 1", ChartType.PIE),
    ("Doanh thu theo bang và thanh toán?",
     "SELECT c.customer_state, f.payment_type, SUM(f.price) AS revenue FROM fact_orders f "
     "JOIN dim_customers c ON f.customer_key=c.customer_key "
     "WHERE c.customer_state IN ('SP','RJ','MG') GROUP BY 1,2", ChartType.GROUPED_BAR),
    ("Giá và phí vận chuyển?", "SELECT price, freight_value FROM fact_orders LIMIT 300", ChartType.SCATTER),
    ("Phân phối số ngày giao hàng?",
     "SELECT delivery_days FROM fact_orders WHERE delivery_days IS NOT NULL LIMIT 1000", ChartType.HISTOGRAM),
    ("Vị trí trung bình theo bang?",
     "SELECT geolocation_state, AVG(geolocation_lat) AS lat, AVG(geolocation_lng) AS lng "
     "FROM dim_geolocation GROUP BY 1", ChartType.MAP),
    ("Một vài mã đơn hàng?", "SELECT order_id, order_status FROM fact_orders LIMIT 5", ChartType.TABLE),
]


@requires_db
@pytest.mark.parametrize("question,sql,expected", E2E, ids=[e[2].value + str(i) for i, e in enumerate(E2E)])
def test_pipeline_returns_chart_and_insights(question, sql, expected):
    llm = ScriptedLLM({question: sql})
    pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    result = pipeline.run(question)
    assert result.success, result.error_message
    assert result.chart_spec.chart_type == expected
    assert isinstance(result.chart, go.Figure)
    assert result.insights.source == "llm" and len(result.insights.bullets) == 3
    assert {"generate_sql", "execute", "chart", "insight"} <= set(result.timings_ms)


@requires_db
def test_pipeline_insight_fallback_when_llm_fails():
    q, sql, _ = E2E[1]
    pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=ScriptedLLM({q: sql}, insight_error=True))
    result = pipeline.run(q)
    assert result.success and result.insights.source == "rule"
    assert result.insights.bullets


@requires_db
def test_pipeline_can_disable_chart_and_insights():
    q, sql, _ = E2E[1]
    llm = ScriptedLLM({q: sql})
    pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm,
                                 enable_chart=False, enable_insights=False)
    result = pipeline.run(q)
    assert result.success and result.chart is None and result.insights is None
    assert llm.insight_calls == 0


@requires_db
def test_failed_query_has_no_chart_or_insight():
    llm = ScriptedLLM({"Xóa dữ liệu": "DELETE FROM fact_orders"})
    result = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm).run("Xóa dữ liệu")
    assert not result.success and result.chart is None and result.insights is None
    assert llm.insight_calls == 0
