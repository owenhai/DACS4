"""Unit tests Tuần 5: logic UI (services), progress_callback và Streamlit AppTest.

Chạy offline hoàn toàn (LLM giả lập bằng ScriptedLLM, DuckDB thật).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import plotly.express as px
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.models.insight_generator import InsightResult
from src.models.text_to_sql import QueryResult, TextToSQLPipeline
from src.ui import history_store, services, styles
from src.visualization.chart_classifier import ChartSpec, ChartType
from src.visualization.chart_generator import apply_theme, build_chart

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_PATH = ROOT_DIR / "app.py"
DB_PATH = ROOT_DIR / "data" / "database" / "olist_analytics.duckdb"
requires_db = pytest.mark.skipif(not DB_PATH.exists(), reason="DuckDB database chưa được tạo")


class ScriptedLLM:
    """Giả lập GeminiClient: trả SQL cho prompt Text-to-SQL, trả bullet cho insight."""

    def __init__(self, sql_by_question: dict[str, str]):
        self.sql_by_question = sql_by_question

    def generate(self, prompt: str, **_kw) -> str:
        if "Pre-computed statistics" in prompt or "Insights (Vietnamese" in prompt:
            return "- Nhận xét 1.\n- Nhận xét 2.\n- Nhận xét 3."
        for q, sql in self.sql_by_question.items():
            if q in prompt:
                return sql
        raise RuntimeError(f"ScriptedLLM: không có kịch bản cho prompt: {prompt[:80]}")


@pytest.fixture(autouse=True)
def _clear_streamlit_cache(tmp_path, monkeypatch):
    monkeypatch.delenv(history_store.HISTORY_DB_ENV_VAR, raising=False)
    monkeypatch.setenv(history_store.HISTORY_BACKEND_ENV_VAR, "sqlite")
    monkeypatch.delenv("MYSQL_HOST", raising=False)
    monkeypatch.setattr(
        history_store, "DEFAULT_HISTORY_DB_PATH", tmp_path / "test_query_history.db"
    )
    monkeypatch.setattr(history_store, "_mysql_schema_ready_key", None)
    monkeypatch.setattr(history_store, "_last_fallback_reason", None)
    st.cache_resource.clear()
    st.cache_data.clear()
    yield
    st.cache_resource.clear()
    st.cache_data.clear()


# ===========================================================================
# Tests cho src/ui/services.py
# ===========================================================================

def test_validate_question_cases():
    ok, err, cleaned = services.validate_question(None)
    assert not ok and err and cleaned == ""

    ok, err, cleaned = services.validate_question("   \n\t  ")
    assert not ok and "Vui lòng" in err and cleaned == ""

    too_long = "a" * (services.MAX_QUESTION_LENGTH + 1)
    ok, err, _ = services.validate_question(too_long)
    assert not ok and str(services.MAX_QUESTION_LENGTH) in err

    ok, err, cleaned = services.validate_question("  Tổng doanh thu?  ")
    assert ok and err is None and cleaned == "Tổng doanh thu?"


def test_friendly_error_categories():
    lvl, msg = services.friendly_error(
        SimpleNamespace(error_type="security", error_message="Blocked DROP", correction_attempts=0)
    )
    assert lvl == "error" and "bảo mật" in msg and "Blocked DROP" in msg

    lvl, msg = services.friendly_error(
        SimpleNamespace(error_type=None, error_message="Loi sinh SQL: 503", correction_attempts=0)
    )
    assert lvl == "warning" and "Gemini" in msg

    lvl, msg = services.friendly_error(
        SimpleNamespace(error_type="timeout", error_message="Timeout 30s", correction_attempts=1)
    )
    assert lvl == "warning" and "quá lâu" in msg

    lvl, msg = services.friendly_error(
        SimpleNamespace(error_type="syntax", error_message="Parser Error", correction_attempts=2)
    )
    assert lvl == "error" and "2 lần" in msg and "Parser Error" in msg


def test_format_timings_order_and_skip_missing():
    items = services.format_timings(
        {"insight": 500, "generate_sql": 1200, "execute": 45},
        total_ms=1745,
    )
    assert items == [
        ("Sinh SQL", "1.20s"),
        ("Thực thi", "0.04s"),
        ("Nhận xét", "0.50s"),
        ("Tổng", "1.75s"),
    ]


def test_dataframe_to_csv_bytes_has_utf8_bom():
    df = pd.DataFrame({"tỉnh": ["Hà Nội"], "doanh_thu": [1000]})
    raw = services.dataframe_to_csv_bytes(df)
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "Hà Nội" in raw.decode("utf-8-sig")


def test_figure_to_html_bytes_valid():
    fig = px.bar(x=["A", "B"], y=[10, 20])
    raw = services.figure_to_html_bytes(fig)
    assert b"<html" in raw.lower()


def test_make_history_entry():
    qr = QueryResult(
        question="Tổng đơn?",
        generated_sql="SELECT 1",
        success=True,
        execution_time_ms=1523.4,
        chart_spec=ChartSpec(ChartType.KPI, reason="1 row"),
    )
    entry = services.make_history_entry(qr)
    assert entry["question"] == "Tổng đơn?"
    assert entry["success"] is True
    assert entry["chart_type"] == "kpi"
    assert entry["total_s"] == 1.52
    assert len(entry["timestamp"]) == 8
    assert entry["result"] is qr


# ===========================================================================
# Tests cho progress_callback trong TextToSQLPipeline
# ===========================================================================

@requires_db
def test_pipeline_progress_callback_order():
    q = "Tổng số đơn hàng?"
    llm = ScriptedLLM({q: "SELECT COUNT(DISTINCT order_id) AS n FROM fact_orders"})
    pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    steps: list[str] = []
    result = pipeline.run(q, progress_callback=steps.append)
    assert result.success
    assert steps == ["generate_sql", "execute", "chart", "insight", "done"]


@requires_db
def test_pipeline_ignores_broken_progress_callback():
    q = "Tổng số đơn hàng?"
    llm = ScriptedLLM({q: "SELECT COUNT(DISTINCT order_id) AS n FROM fact_orders"})
    pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)

    def broken(_step: str) -> None:
        raise RuntimeError("UI closed")

    result = pipeline.run(q, progress_callback=broken)
    assert result.success and result.dataframe is not None


# ===========================================================================
# Tests giao diện bằng Streamlit AppTest
# ===========================================================================

@requires_db
def test_app_initial_load():
    llm = ScriptedLLM({})
    fake_pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    with patch("src.ui.services.build_pipeline", return_value=fake_pipeline):
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at.run()
    assert not at.exception
    assert any("Data Insights Engine" in t.value for t in at.title)


@requires_db
def test_app_click_example_question():
    first_example = services.EXAMPLE_QUESTIONS[0]
    llm = ScriptedLLM({first_example: "SELECT COUNT(DISTINCT order_id) AS n FROM fact_orders"})
    fake_pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    with patch("src.ui.services.build_pipeline", return_value=fake_pipeline):
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at.run()
        at.button(key="ex_0").click().run()
    assert not at.exception
    assert len(at.session_state.history) == 1
    assert at.session_state.history[0]["success"] is True


@requires_db
def test_app_security_question_shows_error():
    q = "Xóa hết đơn hàng"
    llm = ScriptedLLM({q: "DELETE FROM fact_orders"})
    fake_pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    with patch("src.ui.services.build_pipeline", return_value=fake_pipeline):
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at.run()
        at.chat_input[0].set_value(q).run()
    assert not at.exception
    assert len(at.session_state.history) == 1
    assert at.session_state.history[0]["success"] is False
    assert any("bảo mật" in e.value for e in at.error)


def test_app_missing_api_key_shows_friendly_error():
    with patch(
        "src.ui.services.build_pipeline",
        side_effect=ValueError("Không tìm thấy GEMINI_API_KEY"),
    ):
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at.run()
    assert not at.exception
    assert any("GEMINI_API_KEY" in e.value for e in at.error)


# ===========================================================================
# Tests bổ sung cho giao diện nâng cấp
# ===========================================================================

def test_format_compact_number():
    assert services.format_compact_number(13_591_643.7, prefix="R$ ") == "R$ 13,59M"
    assert services.format_compact_number(98666) == "98.666"
    assert services.format_compact_number(4.034) == "4,03"
    assert services.format_compact_number(None) == "—"
    assert services.format_compact_number(float("nan")) == "—"


@requires_db
def test_get_database_overview_and_table_preview():
    ov = services.get_database_overview(DB_PATH)
    assert ov["total_orders"] > 0
    assert ov["total_revenue"] > 0
    assert len(ov["table_counts"]) == 6
    assert set(ov["table_counts"]) >= {
        "fact_orders", "dim_customers", "dim_products",
        "dim_sellers", "dim_date", "dim_geolocation",
    }

    preview = services.get_table_preview("fact_orders", db_path=DB_PATH, limit=5)
    assert len(preview) == 5

    with pytest.raises(ValueError, match="Bảng không hợp lệ"):
        services.get_table_preview("fact_orders; DROP TABLE x", db_path=DB_PATH)


def test_get_schema_summary_structure():
    summary = services.get_schema_summary()
    assert len(summary) == 6
    assert summary[0]["name"] == "fact_orders"
    assert summary[0]["kind"] == "FACT"
    for tbl in summary:
        assert tbl["column_count"] > 0
        assert len(tbl["columns"]) == tbl["column_count"]


def test_build_session_log_df():
    empty_df = services.build_session_log_df([])
    assert empty_df.empty
    assert list(empty_df.columns) == [
        "Thời gian", "Câu hỏi", "Trạng thái", "Biểu đồ", "Tự sửa", "Tổng (s)"
    ]

    qr = QueryResult(
        question="Top 5 danh mục?",
        generated_sql="SELECT 1",
        success=True,
        execution_time_ms=2100.0,
        correction_attempts=1,
        chart_spec=ChartSpec(ChartType.BAR, reason="ok"),
    )
    df = services.build_session_log_df([services.make_history_entry(qr)])
    assert len(df) == 1
    assert df.iloc[0]["Trạng thái"] == "Thành công"
    assert df.iloc[0]["Biểu đồ"] == "Biểu đồ cột"
    assert df.iloc[0]["Tự sửa"] == 1
    assert df.iloc[0]["Tổng (s)"] == 2.1


def test_styles_html_escapes_untrusted_input():
    payload = "<script>alert(1)</script>"
    banner = styles.question_banner_html(payload, "10:00:00")
    assert "<script>" not in banner
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in banner

    card = styles.insights_card_html([payload], source="llm")
    assert "<script>" not in card
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in card


@requires_db
def test_app_click_welcome_card():
    card_q = services.CATEGORIZED_EXAMPLES[0]["question"]
    llm = ScriptedLLM({card_q: "SELECT COUNT(DISTINCT order_id) AS n FROM fact_orders"})
    fake_pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    with patch("src.ui.services.build_pipeline", return_value=fake_pipeline):
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at.run()
        at.button(key="welcome_ex_0").click().run()
    assert not at.exception
    assert len(at.session_state.history) == 1
    assert at.session_state.history[0]["success"] is True


@requires_db
def test_app_switch_workspace_modes():
    q1 = services.EXAMPLE_QUESTIONS[0]
    q2 = services.EXAMPLE_QUESTIONS[1]
    llm = ScriptedLLM({
        q1: "SELECT COUNT(DISTINCT order_id) AS n FROM fact_orders",
        q2: "SELECT product_category_name_english, COUNT(*) AS n FROM dim_products GROUP BY 1 LIMIT 5",
    })
    fake_pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    with patch("src.ui.services.build_pipeline", return_value=fake_pipeline):
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at.run()
        # Tạo 2 lượt truy vấn để kiểm tra luôn biểu đồ latency trong Hệ thống & Hiệu năng
        at.button(key="ex_0").click().run()
        at.button(key="ex_1").click().run()

        at.segmented_control[0].set_value("🗂️ Star Schema & Dữ liệu").run()
        assert not at.exception

        at.segmented_control[0].set_value("🛡️ Hệ thống & Hiệu năng").run()
        assert not at.exception


def test_get_theme_css_light_and_dark():
    light_css = styles.get_theme_css(dark_mode=False)
    dark_css = styles.get_theme_css(dark_mode=True)
    assert ".st-key-sticky_header" in light_css
    assert '[data-testid="stLayoutWrapper"]:has(.st-key-sticky_header)' in light_css
    assert '[data-testid="stToolbar"]' in light_css
    assert "position: sticky" in light_css
    assert "--dacs-bg: #F8FAFC" in light_css
    assert "--dacs-bg: #0B1120" in dark_css
    assert "background-color: #0B1120 !important" in dark_css
    assert "background-color: #0B1120 !important" not in light_css
    assert '[data-testid="stSelectbox"]' in dark_css
    assert '[data-testid="stTab"]' in dark_css
    assert 'button[data-variant="segmented_control"]' in dark_css
    assert ":not(pre) > code" in dark_css
    assert "\n\n" not in light_css
    assert "\n\n" not in dark_css


def test_style_figure_for_theme():
    fig = apply_theme(px.bar(x=["A", "B"], y=[10, 20]), "Demo")
    assert fig.layout.font.color == "#334155"

    # Light mode: giữ nguyên
    light_fig = styles.style_figure_for_theme(fig, dark_mode=False)
    assert light_fig.layout.font.color == "#334155"

    # Dark mode: bản sao đổi màu chữ sáng, bản gốc vẫn giữ màu cũ
    dark_fig = styles.style_figure_for_theme(fig, dark_mode=True)
    assert dark_fig.layout.font.color == "#E2E8F0"
    assert fig.layout.font.color == "#334155"


@requires_db
def test_app_toggle_dark_mode():
    llm = ScriptedLLM({})
    fake_pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    with patch("src.ui.services.build_pipeline", return_value=fake_pipeline):
        at = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at.run()
        assert at.session_state.dark_mode is False

        at.button(key="theme_toggle").click().run()
        assert not at.exception
        assert at.session_state.dark_mode is True

        at.button(key="theme_toggle").click().run()
        assert not at.exception
        assert at.session_state.dark_mode is False


# ===========================================================================
# Tests lưu trữ bền vững lịch sử SQLite
# ===========================================================================

def test_history_store_roundtrip_and_clear(tmp_path):
    db_file = tmp_path / "custom_history.db"
    df = pd.DataFrame({"cat": ["health", "watches"], "rev": [1200.0, 900.0]})
    spec = ChartSpec(
        ChartType.BAR,
        x="cat",
        y="rev",
        reason="So sánh doanh thu",
        roles={"cat": "categorical", "rev": "numeric"},
    )
    chart = build_chart(df, spec, "Top danh mục?")
    qr_ok = QueryResult(
        question="Top danh mục?",
        generated_sql="SELECT cat, rev FROM t",
        dataframe=df,
        success=True,
        execution_time_ms=820.0,
        correction_attempts=0,
        correction_history=[{"attempt": 1, "error_type": None}],
        warnings=["Tự động thêm LIMIT 1000"],
        chart=chart,
        chart_spec=spec,
        insights=InsightResult(
            bullets=["Nhóm health dẫn đầu."],
            statistics={"row_count": 2},
            source="llm",
        ),
        timings_ms={"generate_sql": 450.0, "execute": 12.0},
    )
    qr_sec = QueryResult(
        question="Xóa bảng",
        generated_sql="DELETE FROM fact_orders",
        success=False,
        error_type="security",
        error_message="Blocked DELETE",
        execution_time_ms=15.0,
    )

    e1 = services.make_history_entry(qr_ok)
    e2 = services.make_history_entry(qr_sec)
    id1 = history_store.save_history_entry(e1, model_name="gemini-3.5-flash-lite", db_path=db_file)
    id2 = history_store.save_history_entry(e2, model_name="gemini-3.5-flash-lite", db_path=db_file)
    assert id2 > id1

    loaded = history_store.load_history(limit=10, db_path=db_file)
    assert len(loaded) == 2
    r1 = loaded[0]["result"]
    assert loaded[0]["id"] == id1
    assert loaded[0]["model_name"] == "gemini-3.5-flash-lite"
    assert r1.success is True
    assert list(r1.dataframe["cat"]) == ["health", "watches"]
    assert r1.chart is not None
    assert r1.chart_spec.chart_type == ChartType.BAR
    assert r1.insights.bullets == ["Nhóm health dẫn đầu."]
    assert r1.insights.source == "llm"
    assert r1.warnings == ["Tự động thêm LIMIT 1000"]
    assert r1.timings_ms == {"generate_sql": 450.0, "execute": 12.0}

    r2 = loaded[1]["result"]
    assert r2.success is False
    assert r2.error_type == "security"
    assert "Blocked DELETE" in r2.error_message

    stats = history_store.get_history_stats(db_path=db_file)
    assert stats["exists"] is True
    assert stats["total_entries"] == 2
    assert stats["success_count"] == 1

    metrics = services.compute_history_metrics(loaded)
    assert metrics == {
        "total_queries": 2,
        "first_try_success": 1,
        "corrected_success": 0,
        "blocked_security": 1,
    }

    assert history_store.delete_history_entry(id1, db_path=db_file) is True
    assert len(history_store.load_history(db_path=db_file)) == 1
    assert history_store.clear_history(db_path=db_file) == 1
    assert history_store.load_history(db_path=db_file) == []


@requires_db
def test_app_history_persists_across_reload():
    q0 = services.EXAMPLE_QUESTIONS[0]
    llm = ScriptedLLM({q0: "SELECT COUNT(DISTINCT order_id) AS total_orders FROM fact_orders"})
    fake_pipeline = TextToSQLPipeline(db_path=DB_PATH, llm_client=llm)
    with patch("src.ui.services.build_pipeline", return_value=fake_pipeline):
        at1 = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at1.run()
        at1.button(key="ex_0").click().run()
        assert not at1.exception
        assert len(at1.session_state.history) == 1

        # Giả lập reload / mở lại phiên mới
        at2 = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at2.run()
        assert not at2.exception
        assert len(at2.session_state.history) == 1
        restored = at2.session_state.history[0]
        assert restored["question"] == q0
        assert restored["result"].dataframe is not None
        assert restored["result"].chart is not None
        assert restored["result"].insights is not None

        # Chuyển sang Hệ thống & Hiệu năng kiểm tra metric từ lịch sử đã lưu
        at2.segmented_control[0].set_value("🛡️ Hệ thống & Hiệu năng").run()
        assert not at2.exception
        assert any(m.label == "Tổng truy vấn" and m.value == "1" for m in at2.metric)

        # Xóa lịch sử cũng phải xóa khỏi SQLite và đưa metric về 0
        at2.button(key="clear_history").click().run()
        assert not at2.exception
        assert len(at2.session_state.history) == 0
        assert any(m.label == "Tổng truy vấn" and m.value == "0" for m in at2.metric)

        at3 = AppTest.from_file(str(APP_PATH), default_timeout=60)
        at3.run()
        assert not at3.exception
        assert len(at3.session_state.history) == 0


def test_history_store_mysql_backend_mocked(monkeypatch):
    import pymysql

    monkeypatch.setenv(history_store.HISTORY_BACKEND_ENV_VAR, "auto")
    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_DATABASE", "dacs4_test")
    monkeypatch.setattr(history_store, "_mysql_schema_ready_key", None)

    store: list[dict] = []
    cols = [
        "created_at", "timestamp", "model_name", "question", "generated_sql",
        "success", "error_type", "error_message", "execution_time_ms",
        "correction_attempts", "correction_history_json", "warnings_json",
        "timings_ms_json", "chart_type", "chart_spec_json", "dataframe_json",
        "insights_json",
    ]
    next_id = {"val": 1}

    class _FakeCursor:
        def __init__(self):
            self.lastrowid = 0
            self.rowcount = 0
            self._result = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params=None):
            upper = " ".join(sql.split()).upper()
            if upper.startswith(("CREATE ", "USE ")):
                return
            if upper.startswith("INSERT INTO QUERY_HISTORY"):
                row_id = next_id["val"]
                next_id["val"] += 1
                row = {"id": row_id, **dict(zip(cols, params))}
                store.append(row)
                self.lastrowid = row_id
                self.rowcount = 1
            elif "FROM QUERY_HISTORY ORDER BY ID DESC LIMIT" in upper:
                limit = int(params[0])
                self._result = list(reversed(store))[:limit]
            elif "COALESCE(SUM(CASE WHEN SUCCESS" in upper:
                total = len(store)
                ok = sum(1 for r in store if r["success"])
                self._result = [{"total_entries": total, "success_count": ok}]
            elif "FROM INFORMATION_SCHEMA.TABLES" in upper:
                self._result = [{"size_kb": 16.0}]
            elif upper.startswith("DELETE FROM QUERY_HISTORY WHERE ID ="):
                target_id = int(params[0])
                before = len(store)
                store[:] = [r for r in store if r["id"] != target_id]
                self.rowcount = before - len(store)
            elif upper.startswith("DELETE FROM QUERY_HISTORY"):
                self.rowcount = len(store)
                store.clear()

        def fetchall(self):
            return list(self._result)

        def fetchone(self):
            return self._result[0] if self._result else None

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(pymysql, "connect", lambda **_kw: _FakeConn())

    df = pd.DataFrame({"state": ["SP", "RJ"], "orders": [100, 50]})
    spec = ChartSpec(
        ChartType.BAR, x="state", y="orders",
        roles={"state": "categorical", "orders": "numeric"},
    )
    qr = QueryResult(
        question="Top bang?",
        generated_sql="SELECT state, orders FROM fact_orders",
        dataframe=df,
        success=True,
        execution_time_ms=420.0,
        chart=build_chart(df, spec, "Top bang?"),
        chart_spec=spec,
        insights=InsightResult(bullets=["SP dan dau."], source="llm"),
    )
    entry = services.make_history_entry(qr)
    row_id = history_store.save_history_entry(entry, model_name="gemini-3.5-flash-lite")
    assert row_id == 1

    loaded = history_store.load_history(limit=10)
    assert len(loaded) == 1
    assert loaded[0]["question"] == "Top bang?"
    assert loaded[0]["result"].chart is not None
    assert loaded[0]["result"].insights.bullets == ["SP dan dau."]

    stats = history_store.get_history_stats()
    assert stats["backend"] == "mysql"
    assert stats["fallback_used"] is False
    assert stats["total_entries"] == 1
    assert stats["db_path"] == "127.0.0.1:3306 / dacs4_test"

    assert history_store.delete_history_entry(row_id) is True
    assert history_store.load_history() == []

    history_store.save_history_entry(entry, model_name="gemini-3.5-flash-lite")
    assert history_store.clear_history() == 1


def test_history_store_mysql_falls_back_to_sqlite_on_error(tmp_path, monkeypatch):
    import pymysql

    fb_db = tmp_path / "fb.db"
    monkeypatch.setenv(history_store.HISTORY_BACKEND_ENV_VAR, "auto")
    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_PASSWORD", "super_secret_pw")
    monkeypatch.setenv(history_store.HISTORY_DB_ENV_VAR, str(fb_db))
    monkeypatch.setattr(history_store, "_mysql_schema_ready_key", None)
    monkeypatch.setattr(
        pymysql,
        "connect",
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("Access denied super_secret_pw")),
    )

    qr = QueryResult(
        question="Fallback test?",
        generated_sql="SELECT 1",
        success=True,
        execution_time_ms=110.0,
    )
    entry = services.make_history_entry(qr)
    history_store.save_history_entry(entry, model_name="gemini-3.5-flash-lite")

    loaded = history_store.load_history()
    assert len(loaded) == 1
    assert loaded[0]["question"] == "Fallback test?"

    stats = history_store.get_history_stats()
    assert stats["backend"] == "sqlite"
    assert stats["fallback_used"] is True
    assert stats["total_entries"] == 1
    assert stats["fallback_reason"] is not None
    assert "super_secret_pw" not in stats["fallback_reason"]
    assert "***" in stats["fallback_reason"]


