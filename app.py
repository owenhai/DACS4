"""Giao diện web Streamlit cho DACS4 - Automated Data Insights Engine.

Chạy từ thư mục gốc dự án:
    streamlit run app.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
load_dotenv(Path(_PROJECT_ROOT) / ".env", override=False)

from src.models.insight_generator import format_statistics  # noqa: E402
from src.models.sql_guardrails import format_sql  # noqa: E402
from src.ui import history_store, services, styles  # noqa: E402
from src.visualization.chart_generator import PRIMARY_COLOR, apply_theme  # noqa: E402

MODE_CHAT = "💬 Hỏi đáp Phân tích"
MODE_SCHEMA = "🗂️ Star Schema & Dữ liệu"
MODE_SYSTEM = "🛡️ Hệ thống & Hiệu năng"

st.set_page_config(
    page_title="DACS4 - Data Insights Engine",
    page_icon="📊",
    layout="wide",
)


@st.cache_resource(show_spinner="Đang khởi tạo pipeline...")
def get_pipeline(
    model: str,
    use_cache: bool,
    max_corrections: int,
    enable_insights: bool,
):
    """Khởi tạo và giữ lại pipeline dùng chung giữa các lượt hỏi."""
    return services.build_pipeline(
        model_name=model,
        use_cache=use_cache,
        max_corrections=max_corrections,
        enable_insights=enable_insights,
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_overview(db_path_str: str) -> dict[str, Any]:
    """Đọc các chỉ số tổng quan Olist từ DuckDB và cache trong 5 phút."""
    return services.get_database_overview(db_path_str)


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_table_preview(table_name: str, db_path_str: str) -> pd.DataFrame:
    """Xem trước 10 dòng đầu của bảng hợp lệ trong DuckDB."""
    return services.get_table_preview(table_name, db_path=db_path_str, limit=10)


def _clear_history() -> None:
    try:
        history_store.clear_history()
    except Exception:  # noqa: BLE001
        pass
    st.session_state.history = []


def _toggle_theme() -> None:
    st.session_state.dark_mode = not st.session_state.get("dark_mode", False)


def _queue_question(question: str) -> None:
    """Đưa câu hỏi mẫu vào hàng đợi và chuyển về không gian Hỏi đáp."""
    st.session_state.pending_question = question
    st.session_state.active_mode = MODE_CHAT


def _safe_format_sql(sql: str) -> str:
    try:
        return format_sql(sql) or sql
    except Exception:  # noqa: BLE001
        return sql


def render_result(entry: dict[str, Any], idx: int) -> None:
    """Hiển thị một cặp câu hỏi - câu trả lời trong thẻ phân tích chuyên biệt."""
    result = entry["result"]
    with st.container(border=True):
        st.html(styles.question_banner_html(entry["question"], entry["timestamp"]))
        st.html(
            styles.result_meta_bar_html(
                result, entry, services.CHART_TYPE_LABELS
            )
        )

        if not result.success:
            level, msg = services.friendly_error(result)
            getattr(st, level)(msg)
            if result.generated_sql:
                with st.expander("Câu SQL gần nhất"):
                    st.code(_safe_format_sql(result.generated_sql), language="sql")
            return

        if result.correction_attempts > 0:
            st.info(
                f"🔄 Hệ thống đã tự sửa SQL {result.correction_attempts} lần "
                "để truy vấn thành công."
            )

        tab_chart, tab_data, tab_sql, tab_insights = st.tabs(
            ["📈 Biểu đồ", "📋 Dữ liệu", "🧾 SQL", "💡 Insights"]
        )

        with tab_chart:
            if result.chart is not None:
                chart_fig = styles.style_figure_for_theme(
                    result.chart, bool(st.session_state.get("dark_mode", False))
                )
                st.plotly_chart(
                    chart_fig, width="stretch", key=f"chart_{idx}"
                )
                if result.chart_spec is not None:
                    st.caption(
                        f"Loại biểu đồ: `{result.chart_spec.chart_type.value}` "
                        f"— {result.chart_spec.reason}"
                    )
                st.download_button(
                    "Tải biểu đồ (HTML)",
                    data=services.figure_to_html_bytes(chart_fig),
                    file_name=f"chart_{idx}.html",
                    mime="text/html",
                    key=f"dl_chart_{idx}",
                )
            else:
                st.info("Không có biểu đồ cho kết quả này.")

        with tab_data:
            if result.dataframe is not None:
                df = result.dataframe
                st.caption(f"Hiển thị {len(df):,} dòng × {len(df.columns)} cột")
                st.dataframe(df, width="stretch", hide_index=True)
                st.download_button(
                    "Tải CSV (UTF-8)",
                    data=services.dataframe_to_csv_bytes(df),
                    file_name=f"result_{idx}.csv",
                    mime="text/csv",
                    key=f"dl_csv_{idx}",
                )
            else:
                st.info("Không có dữ liệu bảng.")

        with tab_sql:
            st.code(_safe_format_sql(result.generated_sql), language="sql")
            st.caption("🛡️ Đã kiểm duyệt qua SQL Guardrails (SELECT-only)")
            for warning in result.warnings:
                st.caption(f"⚠️ {warning}")
            if len(result.correction_history) > 1:
                with st.expander("Lịch sử tự sửa SQL"):
                    for step in result.correction_history:
                        st.markdown(
                            f"**Lần {step.get('attempt', '?')}** — "
                            f"Loại lỗi: `{step.get('error_type') or 'không'}`"
                        )
                        if step.get("error"):
                            st.caption(step["error"])
                        if step.get("sql"):
                            st.code(step["sql"], language="sql")

        with tab_insights:
            if result.insights is None:
                st.info("Đã tắt sinh nhận xét.")
            else:
                st.html(
                    styles.insights_card_html(
                        result.insights.bullets, result.insights.source
                    )
                )
                if result.insights.source == "rule":
                    st.caption("Nhận xét sinh theo luật (LLM không khả dụng).")
                if result.insights.statistics:
                    with st.expander("📐 Thống kê tự động (Pandas)"):
                        st.text(format_statistics(result.insights.statistics))

        timing_items = services.format_timings(
            result.timings_ms, result.execution_time_ms
        )
        if timing_items:
            with st.expander("⏱️ Chi tiết độ trễ từng bước"):
                cols = st.columns(len(timing_items))
                for col, (label, val) in zip(cols, timing_items):
                    col.metric(label, val)


def _render_welcome_dashboard(overview: dict[str, Any]) -> None:
    """Màn hình chào mừng gọn gàng theo phong cách BI Dashboard."""
    if overview:
        st.html(styles.kpi_strip_html(overview))

    st.markdown("**🚀 Gợi ý nhanh**")
    cards = services.CATEGORIZED_EXAMPLES
    cols = st.columns(len(cards))
    for idx, (col, card) in enumerate(zip(cols, cards)):
        with col:
            with st.container(border=True):
                st.html(
                    f'<div class="dacs-quick-label">{card["icon"]} {card["category"]}</div>'
                )
                st.button(
                    card["question"],
                    key=f"welcome_ex_{idx}",
                    on_click=_queue_question,
                    args=(card["question"],),
                    width="stretch",
                )


def _render_chat_workspace(
    pipeline: Any, overview: dict[str, Any], selected_model: str = ""
) -> None:
    """Không gian 1: Hỏi đáp phân tích dữ liệu tự nhiên."""
    chat_val = st.chat_input(
        "Đặt câu hỏi về dữ liệu Olist bằng tiếng Việt hoặc tiếng Anh (Enter để gửi)...",
        max_chars=services.MAX_QUESTION_LENGTH,
    )
    raw_question = st.session_state.pending_question or chat_val
    st.session_state.pending_question = None

    if raw_question is not None:
        is_valid, err_msg, clean_q = services.validate_question(raw_question)
        if not is_valid:
            st.warning(err_msg)
        else:
            result = None
            with st.status("Đang xử lý...", expanded=True) as status:
                def _on_step(step: str) -> None:
                    label = services.PIPELINE_STEPS.get(step, step)
                    status.update(label=label)
                    st.write(f"• {label}")

                try:
                    result = pipeline.run(clean_q, progress_callback=_on_step)
                    if result.success:
                        status.update(
                            label="Hoàn tất!", state="complete", expanded=False
                        )
                    else:
                        status.update(
                            label="Truy vấn không thành công",
                            state="error",
                            expanded=False,
                        )
                except Exception as exc:  # noqa: BLE001
                    status.update(
                        label="Đã xảy ra lỗi hệ thống",
                        state="error",
                        expanded=False,
                    )
                    st.error(
                        f"Không thể xử lý câu hỏi do lỗi không mong muốn: {exc}"
                    )

            if result is not None:
                entry = services.make_history_entry(result)
                try:
                    history_store.save_history_entry(
                        entry, model_name=selected_model
                    )
                except Exception:  # noqa: BLE001
                    pass
                st.session_state.history.append(entry)

    if not st.session_state.history:
        _render_welcome_dashboard(overview)
    else:
        total_saved = len(st.session_state.history)
        max_visible = 15
        start_idx = max(0, total_saved - max_visible)
        if start_idx > 0:
            st.caption(
                f"Đang hiển thị {max_visible} kết quả gần nhất "
                f"(tổng {total_saved} câu đã lưu — xem toàn bộ tại mục 🛡️ Hệ thống & Hiệu năng)."
            )
        for idx in range(total_saved - 1, start_idx - 1, -1):
            render_result(st.session_state.history[idx], idx)


def _render_schema_workspace(pipeline: Any, overview: dict[str, Any]) -> None:
    """Không gian 2: Khám phá lược đồ Star Schema & dữ liệu thật trong DuckDB."""
    if overview:
        st.html(styles.kpi_strip_html(overview))

    st.subheader("⭐ Sơ đồ Star Schema (Olist Analytics)")
    schema_summary = services.get_schema_summary()
    table_counts = overview.get("table_counts", {})
    st.html(styles.star_schema_html(schema_summary, table_counts))

    st.subheader("🔍 Khám phá chi tiết từng bảng")
    table_names = [t["name"] for t in schema_summary]
    selected_name = st.selectbox(
        "Chọn bảng trong Star Schema",
        options=table_names,
        index=0,
    )
    selected_table = next(t for t in schema_summary if t["name"] == selected_name)

    with st.container(border=True):
        st.markdown(f"**`{selected_table['name']}`** ({selected_table['kind']})")
        st.write(selected_table["description"])
        if selected_table["grain"]:
            st.caption(f"📌 Mức chi tiết (Grain): {selected_table['grain']}")

        tab_meta, tab_preview = st.tabs(
            ["📖 Từ điển cột (Metadata)", "👀 Xem trước dữ liệu (10 dòng)"]
        )
        with tab_meta:
            st.dataframe(
                pd.DataFrame(selected_table["columns"]),
                width="stretch",
                hide_index=True,
            )
        with tab_preview:
            try:
                preview_df = get_cached_table_preview(
                    selected_table["name"], str(pipeline.db_path)
                )
                st.dataframe(preview_df, width="stretch", hide_index=True)
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Không thể đọc dữ liệu mẫu từ DuckDB: {exc}")


def _render_system_workspace(pipeline: Any) -> None:
    """Không gian 3: Theo dõi kiến trúc pipeline, Guardrails, Self-Correction & hiệu năng."""
    st.subheader("⚙️ Luồng xử lý hệ thống (5 bước)")
    st.html(styles.pipeline_flow_html())

    m = services.compute_history_metrics(st.session_state.history)
    with st.container(border=True):
        st.markdown("**📈 Thống kê Self-Correction (tổng hợp lịch sử đã lưu)**")
        cols = st.columns(4)
        cols[0].metric("Tổng truy vấn", m.get("total_queries", 0))
        cols[1].metric("Thành công lần đầu", m.get("first_try_success", 0))
        cols[2].metric("Tự sửa thành công", m.get("corrected_success", 0))
        cols[3].metric("Bị chặn bảo mật", m.get("blocked_security", 0))

    st.subheader("🛡️ Các lớp bảo vệ SQL Guardrails đang bật")
    st.html(styles.guardrails_grid_html(services.GUARDRAILS_SUMMARY))

    st.subheader("📜 Nhật ký truy vấn & CSDL lưu trữ")
    hist_stats = history_store.get_history_stats()
    backend_name = (
        "MySQL"
        if hist_stats.get("backend") == "mysql"
        else (
            "SQLite · dự phòng khi MySQL chưa sẵn sàng"
            if hist_stats.get("fallback_used")
            else "SQLite"
        )
    )
    with st.container(border=True):
        st.markdown("**🗄️ Vị trí lưu trữ cơ sở dữ liệu**")
        st.markdown(
            f"- **CSDL lịch sử hỏi đáp ({backend_name}):** `{hist_stats['db_path']}` "
            f"({hist_stats['total_entries']} bản ghi · {hist_stats['file_size_kb']} KB)"
        )
        st.markdown(
            f"- **CSDL dữ liệu Olist (DuckDB · chỉ đọc):** `{pipeline.db_path}`"
        )
        if hist_stats.get("fallback_used") and hist_stats.get("fallback_reason"):
            st.caption(
                f"ℹ️ Lý do tạm chuyển sang SQLite: {hist_stats['fallback_reason']}"
            )

    if not st.session_state.history:
        st.info("Chưa có truy vấn nào được lưu.")
        return

    log_df = services.build_session_log_df(st.session_state.history)
    st.dataframe(log_df, width="stretch", hide_index=True)
    st.download_button(
        "Tải nhật ký (CSV)",
        data=services.dataframe_to_csv_bytes(log_df),
        file_name="query_history.csv",
        mime="text/csv",
        key="dl_history_csv",
    )

    if len(log_df) >= 2:
        plot_df = log_df.copy()
        plot_df["Nhãn"] = [
            f"#{i + 1} " + (q[:32] + "…" if len(q) > 32 else q)
            for i, q in enumerate(plot_df["Câu hỏi"])
        ]
        fig = px.bar(
            plot_df,
            x="Tổng (s)",
            y="Nhãn",
            orientation="h",
            color_discrete_sequence=[PRIMARY_COLOR],
            labels={"Tổng (s)": "Thời gian (giây)", "Nhãn": "Câu hỏi"},
        )
        fig.update_layout(height=max(260, 42 * len(plot_df) + 90))
        apply_theme(fig, "So sánh độ trễ các câu hỏi trong phiên")
        chart_fig = styles.style_figure_for_theme(
            fig, bool(st.session_state.get("dark_mode", False))
        )
        st.plotly_chart(chart_fig, width="stretch", key="session_latency_chart")


def main() -> None:
    if "history" not in st.session_state:
        try:
            st.session_state.history = history_store.load_history(limit=50)
        except Exception:  # noqa: BLE001
            st.session_state.history = []
    st.session_state.setdefault("pending_question", None)
    st.session_state.setdefault("active_mode", MODE_CHAT)
    st.session_state.setdefault("dark_mode", False)

    st.markdown(
        styles.get_theme_css(st.session_state.dark_mode),
        unsafe_allow_html=True,
    )

    # Sidebar - Thương hiệu, cấu hình & gợi ý nhanh
    with st.sidebar:
        brand_placeholder = st.empty()
        st.html(styles.sidebar_section_html("Cấu hình AI"))
        model_keys = list(services.MODEL_OPTIONS.keys())
        selected_model = st.selectbox(
            "Mô hình Gemini",
            options=model_keys,
            index=model_keys.index(services.DEFAULT_MODEL),
            format_func=lambda m: services.MODEL_OPTIONS[m],
        )
        use_cache = st.toggle("Cache phản hồi", value=True)
        enable_insights = st.toggle("Sinh nhận xét (Insight)", value=True)
        with st.expander("Tùy chọn nâng cao"):
            max_corrections = st.slider(
                "Số lần tự sửa SQL tối đa", min_value=0, max_value=3, value=3
            )

        st.html(styles.sidebar_section_html("Gợi ý nhanh"))
        for i, q in enumerate(services.EXAMPLE_QUESTIONS):
            st.button(
                q,
                key=f"ex_{i}",
                on_click=_queue_question,
                args=(q,),
                width="stretch",
            )

    # Khởi tạo pipeline (hiển thị hướng dẫn thân thiện nếu thiếu key/DB)
    try:
        pipeline = get_pipeline(
            selected_model, use_cache, max_corrections, enable_insights
        )
    except ValueError as err:
        with brand_placeholder:
            st.html(styles.sidebar_brand_html(db_ok=False, table_count=0))
        st.error(
            f"Thiếu cấu hình API Key: {err}\n\n"
            "Hãy sao chép file `.env.example` thành `.env` ở thư mục gốc và điền `GEMINI_API_KEY`."
        )
        st.stop()
    except FileNotFoundError as err:
        with brand_placeholder:
            st.html(styles.sidebar_brand_html(db_ok=False, table_count=0))
        st.error(
            f"Chưa tìm thấy cơ sở dữ liệu DuckDB: {err}\n\n"
            "Hãy chạy pipeline dữ liệu Tuần 1 trước:\n"
            "`python -m src.data.clean_data` và `python -m src.data.star_schema`."
        )
        st.stop()

    overview = get_cached_overview(str(pipeline.db_path))
    table_count = len(overview.get("table_counts", {}))
    with brand_placeholder:
        st.html(
            styles.sidebar_brand_html(db_ok=bool(overview), table_count=table_count)
        )

    # Sticky Header cố định trên cùng khi cuộn
    with st.container(key="sticky_header"):
        col_title, col_theme = st.columns([5.2, 1], vertical_alignment="center")
        with col_title:
            st.title("Automated Data Insights Engine")
        with col_theme:
            st.button(
                "☀️ Sáng" if st.session_state.dark_mode else "🌙 Tối",
                key="theme_toggle",
                on_click=_toggle_theme,
                width="stretch",
            )

        col_nav, col_meta = st.columns([4.2, 1.8], vertical_alignment="center")
        with col_nav:
            active_mode = st.segmented_control(
                "Chế độ hiển thị",
                options=[MODE_CHAT, MODE_SCHEMA, MODE_SYSTEM],
                selection_mode="single",
                required=True,
                label_visibility="collapsed",
                key="active_mode",
            )
        with col_meta:
            st.html(
                styles.hero_badges_html(bool(overview), table_count, selected_model)
            )

    st.html(styles.hero_subtitle_html())

    if active_mode == MODE_SCHEMA:
        _render_schema_workspace(pipeline, overview)
    elif active_mode == MODE_SYSTEM:
        _render_system_workspace(pipeline)
    else:
        _render_chat_workspace(pipeline, overview, selected_model)

    # Sidebar - Lịch sử đã lưu
    with st.sidebar:
        hist_count = len(st.session_state.history)
        hist_label = (
            f"Lịch sử đã lưu ({hist_count})" if hist_count else "Lịch sử phiên"
        )
        st.html(styles.sidebar_section_html(hist_label))
        if not st.session_state.history:
            st.caption("Chưa có câu hỏi nào.")
        else:
            today_prefix = datetime.now().strftime("%Y-%m-%d")
            for item in reversed(st.session_state.history[-5:]):
                icon = "✅" if item["success"] else "❌"
                created_at = str(item.get("created_at") or "")
                if (
                    created_at
                    and len(created_at) >= 16
                    and not created_at.startswith(today_prefix)
                ):
                    dt_label = (
                        f"{created_at[8:10]}/{created_at[5:7]} {created_at[11:16]}"
                    )
                else:
                    dt_label = item["timestamp"]
                q_short = (
                    item["question"][:38] + "…"
                    if len(item["question"]) > 38
                    else item["question"]
                )
                st.caption(f"{icon} [{dt_label}] {q_short}")
            st.button(
                "Xóa lịch sử",
                key="clear_history",
                on_click=_clear_history,
                width="stretch",
            )


if __name__ == "__main__":
    main()
