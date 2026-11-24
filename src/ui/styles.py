"""CSS tập trung (Light/Dark + Sticky Header) và HTML component builders an toàn.

Mọi giá trị động từ người dùng hoặc kết quả truy vấn đều được escape qua
``html.escape`` trước khi đưa vào HTML.
"""

from __future__ import annotations

import html
from typing import Any

import plotly.graph_objects as go

from src.ui.services import format_compact_number


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


# ===========================================================================
# Theme CSS (chú ý không để dòng trống trong thẻ <style> để Markdown giữ nguyên khối)
# ===========================================================================

_LIGHT_VARS = """--dacs-bg: #F8FAFC;
--dacs-surface: #FFFFFF;
--dacs-surface-alt: #F8FAFC;
--dacs-border: #E2E8F0;
--dacs-border-soft: #F1F5F9;
--dacs-text: #0F172A;
--dacs-muted: #475569;
--dacs-dim: #64748B;
--dacs-header-bg: rgba(248, 250, 252, 0.92);
--dacs-h1-grad: linear-gradient(120deg, #0F172A 0%, #1E3A8A 55%, #2563EB 100%);
--dacs-eyebrow-bg: #EFF6FF;
--dacs-eyebrow-text: #1E3A8A;
--dacs-eyebrow-border: #BFDBFE;
--dacs-slate-bg: #F1F5F9;
--dacs-slate-text: #334155;
--dacs-slate-border: #CBD5E1;
--dacs-fact-bg: linear-gradient(135deg, #F8FBFF 0%, #FFFFFF 100%);
--dacs-insight-bg: linear-gradient(135deg, #F0F7FF 0%, #F8FAFF 100%);
--dacs-insight-border: #DBEAFE;
--dacs-insight-title: #1E3A8A;
--dacs-insight-text: #1E293B;
--dacs-shadow: 0 1px 3px rgba(15, 23, 42, 0.05), 0 4px 12px rgba(15, 23, 42, 0.03);
--dacs-header-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
--dacs-primary-bg: #EFF6FF;
--dacs-primary-text: #1D4ED8;
--dacs-primary-border: #BFDBFE;
--dacs-emerald-bg: #ECFDF5;
--dacs-emerald-text: #047857;
--dacs-emerald-border: #A7F3D0;
--dacs-amber-bg: #FFFBEB;
--dacs-amber-text: #B45309;
--dacs-amber-border: #FDE68A;
--dacs-danger-bg: #FEF2F2;
--dacs-danger-text: #B91C1C;
--dacs-danger-border: #FECACA;"""

_DARK_VARS = """--dacs-bg: #0B1120;
--dacs-surface: #111827;
--dacs-surface-alt: #1E293B;
--dacs-border: #1E293B;
--dacs-border-soft: #334155;
--dacs-text: #F1F5F9;
--dacs-muted: #94A3B8;
--dacs-dim: #94A3B8;
--dacs-header-bg: rgba(11, 17, 32, 0.92);
--dacs-h1-grad: linear-gradient(120deg, #F8FAFC 0%, #93C5FD 60%, #60A5FA 100%);
--dacs-eyebrow-bg: rgba(37, 99, 235, 0.18);
--dacs-eyebrow-text: #93C5FD;
--dacs-eyebrow-border: rgba(59, 130, 246, 0.4);
--dacs-slate-bg: #1E293B;
--dacs-slate-text: #E2E8F0;
--dacs-slate-border: #334155;
--dacs-fact-bg: linear-gradient(135deg, #172554 0%, #111827 100%);
--dacs-insight-bg: linear-gradient(135deg, #172554 0%, #0F172A 100%);
--dacs-insight-border: #1E3A8A;
--dacs-insight-title: #93C5FD;
--dacs-insight-text: #E2E8F0;
--dacs-shadow: 0 2px 6px rgba(0, 0, 0, 0.35), 0 6px 18px rgba(0, 0, 0, 0.25);
--dacs-header-shadow: 0 4px 18px rgba(0, 0, 0, 0.4);
--dacs-primary-bg: rgba(59, 130, 246, 0.18);
--dacs-primary-text: #93C5FD;
--dacs-primary-border: rgba(96, 165, 250, 0.35);
--dacs-emerald-bg: rgba(16, 185, 129, 0.16);
--dacs-emerald-text: #6EE7B7;
--dacs-emerald-border: rgba(52, 211, 153, 0.35);
--dacs-amber-bg: rgba(245, 158, 11, 0.18);
--dacs-amber-text: #FCD34D;
--dacs-amber-border: rgba(251, 191, 36, 0.35);
--dacs-danger-bg: rgba(239, 68, 68, 0.18);
--dacs-danger-text: #FCA5A5;
--dacs-danger-border: rgba(248, 113, 113, 0.35);"""

_DARK_WIDGET_OVERRIDES = """.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stBottom"], [data-testid="stBottomBlockContainer"] {
    background-color: #0B1120 !important;
    color: #F1F5F9 !important;
}
[data-testid="stHeader"] button, [data-testid="stHeader"] svg,
[data-testid="stToolbar"] button, [data-testid="stToolbar"] svg {
    color: #E2E8F0 !important;
    fill: #E2E8F0 !important;
}
[data-testid="stSidebar"] {
    background-color: #0F172A !important;
    border-right: 1px solid #1E293B !important;
}
[data-testid="stSidebar"] * {
    color: #E2E8F0;
}
[data-testid="stSidebar"] .stButton > button {
    border-color: #334155 !important;
    background-color: #1E293B !important;
    color: #E2E8F0 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    border-color: #3B82F6 !important;
    border-left-color: #60A5FA !important;
    background-color: #1E3A8A !important;
    color: #FFFFFF !important;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #1E293B !important;
    background-color: #111827 !important;
}
[data-testid="stExpander"] {
    background-color: #111827 !important;
    border-color: #334155 !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {
    color: #E2E8F0 !important;
}
[data-testid="stCode"], [data-testid="stCode"] pre {
    background-color: #0F172A !important;
    border-color: #334155 !important;
    color: #E2E8F0 !important;
}
[data-testid="stBaseButton-secondary"], button[kind="secondary"] {
    background-color: #1E293B !important;
    border-color: #334155 !important;
    color: #E2E8F0 !important;
}
[data-testid="stBaseButton-secondary"]:hover, button[kind="secondary"]:hover {
    border-color: #60A5FA !important;
    background-color: #1E3A8A !important;
    color: #FFFFFF !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
    background-color: #111827 !important;
    border-color: #334155 !important;
    color: #CBD5E1 !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] * {
    color: #CBD5E1 !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover,
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-hovered] {
    background-color: #1E293B !important;
    border-color: #475569 !important;
    color: #F8FAFC !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover *,
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-hovered] * {
    color: #F8FAFC !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected],
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-checked="true"] {
    background-color: #1E3A8A !important;
    border-color: #3B82F6 !important;
    color: #FFFFFF !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected] *,
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-checked="true"] * {
    color: #FFFFFF !important;
}
[data-testid="stSelectbox"] [role="group"] {
    background-color: #1E293B !important;
    border-color: #334155 !important;
}
[data-testid="stSelectbox"] [role="group"][data-focus-within] {
    border-color: #3B82F6 !important;
}
[data-testid="stSelectbox"] input,
[data-testid="stSelectbox"] [role="combobox"] {
    color: #F8FAFC !important;
    -webkit-text-fill-color: #F8FAFC !important;
    caret-color: #60A5FA !important;
}
[data-testid="stSelectbox"] button,
[data-testid="stSelectbox"] svg {
    color: #CBD5E1 !important;
    fill: #CBD5E1 !important;
}
[data-testid="stSelectboxVirtualDropdown"],
[data-testid="stSelectboxVirtualDropdown"] [role="listbox"] {
    background-color: #1E293B !important;
    border: 1px solid #334155 !important;
    color: #F8FAFC !important;
}
[data-testid="stSelectboxVirtualDropdown"] [role="option"] {
    background-color: transparent !important;
    color: #E2E8F0 !important;
}
[data-testid="stSelectboxVirtualDropdown"] [role="option"][data-hovered] [data-item-hl],
[data-testid="stSelectboxVirtualDropdown"] [role="option"][data-focused] [data-item-hl],
[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"] [data-item-hl] {
    background-color: #1E3A8A !important;
    color: #FFFFFF !important;
}
[data-testid="stChatInput"], [data-testid="stChatInput"] > div, [data-testid="stChatInputTextArea"] {
    background-color: #111827 !important;
    border-color: #334155 !important;
    color: #F8FAFC !important;
}
[data-testid="stChatInputTextArea"]::placeholder {
    color: #94A3B8 !important;
}
[data-testid="stMetricValue"], [data-testid="stMetricLabel"],
.stMarkdown p, .stMarkdown li, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4,
.stCaptionContainer, [data-testid="stCaptionContainer"], label {
    color: #E2E8F0 !important;
}
[data-testid="stTabs"] [role="tablist"]::after {
    background-color: #1E293B !important;
}
[data-testid="stTab"],
[data-testid="stTab"] p,
[data-testid="stTab"] span {
    color: #94A3B8 !important;
}
[data-testid="stTab"]:hover,
[data-testid="stTab"]:hover p,
[data-testid="stTab"][data-hovered],
[data-testid="stTab"][data-hovered] p {
    color: #E2E8F0 !important;
}
[data-testid="stTab"][aria-selected="true"],
[data-testid="stTab"][aria-selected="true"] p,
[data-testid="stTab"][data-selected],
[data-testid="stTab"][data-selected] p {
    color: #60A5FA !important;
}
[data-testid="stTab"][aria-selected="true"] .react-aria-SelectionIndicator,
[data-testid="stTab"][data-selected] .react-aria-SelectionIndicator {
    background-color: #60A5FA !important;
}
:not(pre) > code {
    background-color: #1E293B !important;
    color: #93C5FD !important;
    border: 1px solid #334155 !important;
    border-radius: 5px !important;
    padding: 0.1em 0.38em !important;
}
[data-testid="stDownloadButton"] button {
    background-color: #1E293B !important;
    border-color: #334155 !important;
    color: #E2E8F0 !important;
}
[data-testid="stDownloadButton"] button:hover {
    border-color: #60A5FA !important;
    background-color: #1E3A8A !important;
    color: #FFFFFF !important;
}
[data-testid="stAlert"] p, [data-testid="stAlert"] div {
    color: #E2E8F0 !important;
}
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    filter: invert(0.9) hue-rotate(180deg);
}"""

_BASE_CSS_TEMPLATE = """<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
:root {{
{vars_block}
}}
html, body, .stApp {{
    font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    background-color: var(--dacs-bg);
    color: var(--dacs-text);
}}
code, pre, [data-testid="stCode"] {{
    font-family: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace !important;
}}
[data-testid="stHeader"],
[data-testid="stToolbar"],
.stAppToolbar {{
    background: transparent !important;
    pointer-events: none !important;
}}
[data-testid="stHeader"] button,
[data-testid="stToolbar"] button,
[data-testid="stMainMenu"],
[data-testid="stExpandSidebarButton"],
[data-testid="stStatusWidget"] {{
    pointer-events: auto !important;
}}
[data-testid="stAppDeployButton"] {{
    display: none !important;
}}
.block-container {{
    max-width: 1280px;
    padding-top: 0.45rem !important;
    padding-bottom: 2.5rem !important;
}}
[data-testid="stLayoutWrapper"]:has(.st-key-sticky_header) {{
    position: sticky !important;
    top: 0 !important;
    z-index: 999 !important;
    background: var(--dacs-header-bg) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border-bottom: 1px solid var(--dacs-border) !important;
    box-shadow: var(--dacs-header-shadow) !important;
    padding: 0.5rem 0 0.6rem 0 !important;
    margin-bottom: 0.45rem !important;
}}
.st-key-sticky_header [data-testid="stHeadingWithActionElements"] h1 {{
    font-size: 1.42rem !important;
    margin: 0 !important;
    padding: 0 !important;
}}
[data-testid="stHeadingWithActionElements"] h1 {{
    font-size: 1.82rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.025em !important;
    line-height: 1.18 !important;
    padding: 0.05rem 0 !important;
    margin-bottom: 0.1rem !important;
    background: var(--dacs-h1-grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}
[data-testid="stSidebar"] {{
    background-color: var(--dacs-surface);
    border-right: 1px solid var(--dacs-border);
}}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
    padding-top: 1rem;
}}
[data-testid="stSidebar"] .stButton > button {{
    text-align: left !important;
    justify-content: flex-start !important;
    border-radius: 9px !important;
    border: 1px solid var(--dacs-border) !important;
    border-left: 3px solid transparent !important;
    background-color: var(--dacs-surface-alt) !important;
    color: var(--dacs-text) !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 0.42rem 0.7rem !important;
    transition: all 0.15s ease !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    border-color: #BFDBFE !important;
    border-left-color: #2563EB !important;
    background-color: #EFF6FF !important;
    color: #1D4ED8 !important;
}}
[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 14px !important;
    border-color: var(--dacs-border) !important;
    background-color: var(--dacs-surface) !important;
    box-shadow: var(--dacs-shadow) !important;
}}
.stTabs [data-baseweb="tab-list"] {{
    gap: 0.4rem;
    border-bottom: 1px solid var(--dacs-border);
}}
.stTabs [data-baseweb="tab"] {{
    padding: 0.5rem 0.9rem;
    font-weight: 600;
    color: var(--dacs-muted);
}}
.stTabs [aria-selected="true"] {{
    color: #2563EB !important;
}}
[data-testid="stTab"] {{
    font-weight: 600;
}}
.dacs-sidebar-brand {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.45rem;
    padding: 0.85rem 0.95rem;
    border-radius: 12px;
    background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.14);
    margin-bottom: 0.65rem;
}}
.dacs-sidebar-title {{
    font-size: 0.98rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.01em;
    white-space: nowrap;
}}
.dacs-sidebar-sub {{
    font-size: 0.75rem;
    color: #CBD5E1;
    margin-top: 2px;
}}
.dacs-side-label {{
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--dacs-dim);
    margin: 0.75rem 0 0.35rem 0;
}}
.dacs-status-pill {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: 999px;
    white-space: nowrap;
    background: rgba(16, 185, 129, 0.18);
    color: #6EE7B7;
    border: 1px solid rgba(110, 231, 183, 0.35);
}}
.dacs-status-pill.is-warn {{
    background: rgba(245, 158, 11, 0.18);
    color: #FDE68A;
    border-color: rgba(253, 230, 138, 0.4);
}}
.dacs-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #34D399;
    display: inline-block;
}}
.dacs-status-pill.is-warn .dacs-dot {{
    background: #FBBF24;
}}
.dacs-hero-eyebrow {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    background: var(--dacs-eyebrow-bg);
    color: var(--dacs-eyebrow-text);
    border: 1px solid var(--dacs-eyebrow-border);
    white-space: nowrap;
}}
.dacs-quick-label {{
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--dacs-text);
    margin-bottom: 0.35rem;
}}
.dacs-badge-row {{
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    justify-content: flex-end;
    gap: 0.4rem;
}}
.dacs-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    line-height: 1.4;
    border: 1px solid transparent;
    white-space: nowrap;
}}
.dacs-badge--primary {{
    background: var(--dacs-primary-bg);
    color: var(--dacs-primary-text);
    border-color: var(--dacs-primary-border);
}}
.dacs-badge--emerald {{
    background: var(--dacs-emerald-bg);
    color: var(--dacs-emerald-text);
    border-color: var(--dacs-emerald-border);
}}
.dacs-badge--slate {{
    background: var(--dacs-slate-bg);
    color: var(--dacs-slate-text);
    border-color: var(--dacs-slate-border);
}}
.dacs-badge--amber {{
    background: var(--dacs-amber-bg);
    color: var(--dacs-amber-text);
    border-color: var(--dacs-amber-border);
}}
.dacs-badge--danger {{
    background: var(--dacs-danger-bg);
    color: var(--dacs-danger-text);
    border-color: var(--dacs-danger-border);
}}
.dacs-subtitle {{
    color: var(--dacs-muted);
    font-size: 0.92rem;
    line-height: 1.45;
    margin: 0.15rem 0 0.65rem 0;
}}
.dacs-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
    margin: 0.25rem 0 0.9rem 0;
}}
.dacs-kpi-card {{
    background: var(--dacs-surface);
    border: 1px solid var(--dacs-border);
    border-top: 3px solid #2563EB;
    border-radius: 13px;
    padding: 0.9rem 1rem;
    box-shadow: var(--dacs-shadow);
}}
.dacs-kpi-card.accent-emerald {{ border-top-color: #10B981; }}
.dacs-kpi-card.accent-amber {{ border-top-color: #F59E0B; }}
.dacs-kpi-card.accent-violet {{ border-top-color: #8B5CF6; }}
.dacs-kpi-label {{
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--dacs-dim);
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
.dacs-kpi-value {{
    font-size: 1.45rem;
    font-weight: 800;
    color: var(--dacs-text);
    margin: 0.25rem 0 0.15rem 0;
    line-height: 1.25;
    font-variant-numeric: tabular-nums;
}}
.dacs-kpi-value.is-range {{
    font-size: 1.08rem;
    white-space: nowrap;
    padding: 0.22rem 0 0.12rem 0;
}}
.dacs-kpi-sub {{
    font-size: 0.78rem;
    color: var(--dacs-muted);
}}
.dacs-pipeline {{
    display: flex;
    align-items: stretch;
    gap: 0.45rem;
    background: var(--dacs-surface);
    border: 1px solid var(--dacs-border);
    border-radius: 14px;
    padding: 0.85rem 1rem;
    margin: 0.25rem 0 1.1rem 0;
    box-shadow: var(--dacs-shadow);
}}
.dacs-step {{
    flex: 1 1 0;
    display: flex;
    align-items: flex-start;
    gap: 0.55rem;
    padding: 0.35rem 0.4rem;
    border-radius: 10px;
    background: var(--dacs-surface-alt);
    border: 1px solid var(--dacs-border-soft);
}}
.dacs-step-num {{
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: #2563EB;
    color: #FFFFFF;
    font-size: 0.75rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 1px;
}}
.dacs-step-title {{
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--dacs-text);
}}
.dacs-step-desc {{
    font-size: 0.74rem;
    color: var(--dacs-muted);
    line-height: 1.35;
}}
.dacs-step-arrow {{
    display: flex;
    align-items: center;
    color: #94A3B8;
    font-weight: 700;
    font-size: 1rem;
}}
.dacs-question-banner {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.65rem 0.9rem;
    background: var(--dacs-surface-alt);
    border: 1px solid var(--dacs-border);
    border-radius: 10px;
    margin-bottom: 0.6rem;
}}
.dacs-question-text {{
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--dacs-text);
}}
.dacs-question-time {{
    font-size: 0.78rem;
    color: var(--dacs-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}}
.dacs-meta-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-bottom: 0.65rem;
}}
.dacs-insight-card {{
    background: var(--dacs-insight-bg);
    border: 1px solid var(--dacs-insight-border);
    border-left: 4px solid #2563EB;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.65rem;
}}
.dacs-insight-card.is-compact {{
    padding: 0.55rem 0.9rem;
}}
.dacs-insight-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.35rem;
}}
.dacs-insight-title {{
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--dacs-insight-title);
}}
.dacs-insight-list {{
    margin: 0;
    padding-left: 1.15rem;
    color: var(--dacs-insight-text);
    font-size: 0.92rem;
    line-height: 1.55;
}}
.dacs-insight-list li + li {{
    margin-top: 0.28rem;
}}
.dacs-schema-wrap {{
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    margin: 0.35rem 0 1rem 0;
}}
.dacs-schema-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.85rem;
}}
.dacs-schema-card {{
    background: var(--dacs-surface);
    border: 1px solid var(--dacs-border);
    border-radius: 12px;
    padding: 0.85rem 1rem;
    box-shadow: var(--dacs-shadow);
}}
.dacs-schema-card.is-fact {{
    border: 2px solid #2563EB;
    background: var(--dacs-fact-bg);
}}
.dacs-schema-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.35rem;
}}
.dacs-schema-name {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--dacs-text);
}}
.dacs-schema-desc {{
    font-size: 0.8rem;
    color: var(--dacs-muted);
    line-height: 1.4;
    margin-bottom: 0.45rem;
}}
.dacs-schema-meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    font-size: 0.74rem;
    color: var(--dacs-dim);
}}
.dacs-guard-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.85rem;
    margin: 0.35rem 0 1rem 0;
}}
.dacs-guard-card {{
    background: var(--dacs-surface);
    border: 1px solid var(--dacs-border);
    border-left: 4px solid #10B981;
    border-radius: 12px;
    padding: 0.8rem 0.95rem;
    box-shadow: var(--dacs-shadow);
}}
.dacs-guard-title {{
    font-size: 0.88rem;
    font-weight: 700;
    color: var(--dacs-text);
    margin-bottom: 0.25rem;
}}
.dacs-guard-desc {{
    font-size: 0.8rem;
    color: var(--dacs-muted);
    line-height: 1.45;
}}{dark_overrides}
@media (max-width: 1080px) {{
    [data-testid="stLayoutWrapper"]:has(.st-key-sticky_header) {{ padding-right: 2.2rem !important; }}
}}
@media (max-width: 900px) {{
    .dacs-kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .dacs-pipeline {{ flex-direction: column; }}
    .dacs-step-arrow {{ display: none; }}
    .dacs-schema-grid, .dacs-guard-grid {{ grid-template-columns: 1fr; }}
    .dacs-badge-row {{ justify-content: flex-start; }}
}}
@media (max-width: 600px) {{
    .dacs-kpi-grid {{ grid-template-columns: 1fr; }}
    .st-key-sticky_header [data-testid="stHeadingWithActionElements"] h1 {{ font-size: 1.25rem !important; }}
}}
</style>"""


def get_theme_css(dark_mode: bool = False) -> str:
    """Trả về chuỗi CSS đầy đủ cho chế độ Sáng hoặc Tối kèm Sticky Header."""
    return _BASE_CSS_TEMPLATE.format(
        vars_block=_DARK_VARS if dark_mode else _LIGHT_VARS,
        dark_overrides=f"\n{_DARK_WIDGET_OVERRIDES}" if dark_mode else "",
    )


CUSTOM_CSS = get_theme_css(False)


def style_figure_for_theme(fig: Any, dark_mode: bool) -> Any:
    """Trả về bản sao Plotly Figure đã chỉnh màu chữ/trục theo chế độ Sáng/Tối."""
    if fig is None or not dark_mode:
        return fig

    styled = go.Figure(fig)
    styled.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#E2E8F0"},
        title={"font": {"color": "#F8FAFC"}},
        legend={"font": {"color": "#E2E8F0"}},
        hoverlabel={
            "bgcolor": "#1E293B",
            "bordercolor": "#475569",
            "font": {"color": "#F8FAFC"},
        },
    )
    styled.update_xaxes(
        linecolor="#334155",
        tickfont={"color": "#CBD5E1"},
        title_font={"color": "#E2E8F0"},
    )
    styled.update_yaxes(
        gridcolor="#1E293B",
        tickfont={"color": "#CBD5E1"},
        title_font={"color": "#E2E8F0"},
    )
    for trace in styled.data:
        if getattr(trace, "type", None) == "table":
            n_cells = len(trace.cells.values[0]) if trace.cells and trace.cells.values else 0
            trace.cells.fill.color = [["#0F172A", "#111827"] * (n_cells // 2 + 1)]
            trace.cells.font = {"color": "#E2E8F0"}
        elif getattr(trace, "type", None) == "indicator":
            trace.title = {**(trace.title.to_plotly_json() if trace.title else {}), "font": {"color": "#CBD5E1", "size": 15}}
    return styled


# ===========================================================================
# HTML Component Builders
# ===========================================================================

def sidebar_brand_html(db_ok: bool, table_count: int) -> str:
    """Thẻ thương hiệu và trạng thái CSDL ở đầu thanh bên."""
    status_cls = "dacs-status-pill" if db_ok else "dacs-status-pill is-warn"
    status_text = f"DuckDB · {table_count} bảng" if db_ok else "Chưa kết nối DB"
    return (
        '<div class="dacs-sidebar-brand">'
        '<div>'
        '<div class="dacs-sidebar-title">📊 DACS4 Insights</div>'
        '<div class="dacs-sidebar-sub">Olist Star Schema</div>'
        '</div>'
        f'<span class="{status_cls}"><span class="dacs-dot"></span>{_esc(status_text)}</span>'
        '</div>'
    )


def sidebar_section_html(label: str) -> str:
    """Nhãn phân mục gọn trong thanh bên."""
    return f'<div class="dacs-side-label">{_esc(label)}</div>'


def hero_badges_html(db_ok: bool, table_count: int, model_name: str) -> str:
    """Hàng tag nhỏ đặt gọn bên phải thanh điều hướng trên Sticky Header."""
    del db_ok, table_count  # Trạng thái DB và nhãn DACS4 đã hiển thị ở thẻ thương hiệu sidebar
    return (
        '<div class="dacs-badge-row">'
        f'<span class="dacs-badge dacs-badge--slate">🤖 {_esc(model_name)}</span>'
        '</div>'
    )


def hero_subtitle_html() -> str:
    """Mô tả ngắn gọn 1 câu ngay dưới Sticky Header (cuộn đi tự nhiên)."""
    return (
        '<p class="dacs-subtitle">'
        'Hỏi đáp dữ liệu Olist bằng tiếng Việt/Anh — tự động sinh SQL an toàn, vẽ biểu đồ Plotly và tóm tắt insight.'
        '</p>'
    )


def kpi_strip_html(overview: dict[str, Any]) -> str:
    """Dải 4 thẻ KPI tổng quan dữ liệu thật từ DuckDB."""
    orders = format_compact_number(overview.get("total_orders"))
    items = format_compact_number(overview.get("total_items"))
    revenue = format_compact_number(overview.get("total_revenue"), prefix="R$ ")
    customers = format_compact_number(overview.get("total_customers"))
    review = format_compact_number(overview.get("avg_review"))
    products = format_compact_number(overview.get("total_products"))
    sellers = format_compact_number(overview.get("total_sellers"))
    d_min = _esc(overview.get("date_min", "—"))
    d_max = _esc(overview.get("date_max", "—"))
    n_tables = len(overview.get("table_counts", {})) or 6

    cards = [
        ("Đơn hàng Olist", orders, f"{items} dòng sản phẩm · {customers} khách", "", ""),
        ("Tổng doanh thu", revenue, f"{products} sản phẩm · {sellers} người bán", "accent-emerald", ""),
        ("Điểm đánh giá TB", f"{review} / 5" if review != "—" else "—", "Thang điểm hài lòng khách hàng", "accent-amber", ""),
        ("Phạm vi & Lược đồ", f"{d_min} → {d_max}", f"Star Schema ({n_tables} bảng DuckDB)", "accent-violet", "is-range"),
    ]
    inner = "".join(
        f'<div class="dacs-kpi-card {cls}">'
        f'<div class="dacs-kpi-label">{_esc(label)}</div>'
        f'<div class="dacs-kpi-value {val_cls}">{_esc(val)}</div>'
        f'<div class="dacs-kpi-sub">{_esc(sub)}</div>'
        '</div>'
        for label, val, sub, cls, val_cls in cards
    )
    return f'<div class="dacs-kpi-grid">{inner}</div>'


def pipeline_flow_html() -> str:
    """Sơ đồ 5 bước kiến trúc Text-to-SQL."""
    steps = [
        ("1", "Text-to-SQL", "Gemini + Schema Linking & Few-shot"),
        ("2", "SQL Guardrails", "Chỉ cho phép SELECT, chặn injection"),
        ("3", "DuckDB & Tự sửa", "Thực thi OLAP, lặp sửa lỗi tối đa 3 lần"),
        ("4", "Auto Chart", "Phân loại & vẽ biểu đồ Plotly tự động"),
        ("5", "Insight AI", "Thống kê Pandas + tóm tắt tiếng Việt"),
    ]
    parts: list[str] = []
    for i, (num, title, desc) in enumerate(steps):
        if i > 0:
            parts.append('<div class="dacs-step-arrow">→</div>')
        parts.append(
            '<div class="dacs-step">'
            f'<div class="dacs-step-num">{_esc(num)}</div>'
            '<div>'
            f'<div class="dacs-step-title">{_esc(title)}</div>'
            f'<div class="dacs-step-desc">{_esc(desc)}</div>'
            '</div>'
            '</div>'
        )
    return f'<div class="dacs-pipeline">{"".join(parts)}</div>'


def question_banner_html(question: str, timestamp: str) -> str:
    """Dải tiêu đề câu hỏi của một thẻ kết quả."""
    return (
        '<div class="dacs-question-banner">'
        f'<div class="dacs-question-text">🙋 {_esc(question)}</div>'
        f'<div class="dacs-question-time">🕒 {_esc(timestamp)}</div>'
        '</div>'
    )


def result_meta_bar_html(
    result: Any,
    entry: dict[str, Any],
    chart_labels: dict[str, tuple[str, str]],
) -> str:
    """Thanh badge tóm tắt trạng thái, loại biểu đồ, độ trễ và số dòng của kết quả."""
    success = bool(getattr(result, "success", False))
    badges: list[str] = []
    if success:
        badges.append('<span class="dacs-badge dacs-badge--emerald">✓ Thành công</span>')
    else:
        err_type = getattr(result, "error_type", None)
        label = "🔒 Bị chặn bảo mật" if err_type == "security" else "✕ Không thành công"
        badges.append(f'<span class="dacs-badge dacs-badge--danger">{label}</span>')

    ct = entry.get("chart_type")
    if ct:
        icon, ct_name = chart_labels.get(ct, ("📊", ct))
        badges.append(f'<span class="dacs-badge dacs-badge--primary">{_esc(icon)} {_esc(ct_name)}</span>')

    total_ms = getattr(result, "execution_time_ms", 0.0) or 0.0
    badges.append(f'<span class="dacs-badge dacs-badge--slate">⏱ {total_ms / 1000:.2f}s</span>')

    df = getattr(result, "dataframe", None)
    if success and df is not None:
        badges.append(f'<span class="dacs-badge dacs-badge--slate">📋 {len(df):,} dòng</span>')

    attempts = int(getattr(result, "correction_attempts", 0) or 0)
    if attempts > 0:
        badges.append(f'<span class="dacs-badge dacs-badge--amber">🔄 Tự sửa {attempts} lần</span>')

    return f'<div class="dacs-meta-bar">{"".join(badges)}</div>'


def insights_card_html(bullets: list[str], source: str, compact: bool = False) -> str:
    """Khung hiển thị các nhận xét insight nổi bật."""
    if not bullets:
        return ""
    src_badge = (
        '<span class="dacs-badge dacs-badge--primary">✨ Gemini Flash</span>'
        if source == "llm"
        else '<span class="dacs-badge dacs-badge--slate">📐 Thống kê tự động</span>'
    )
    title = "Tóm tắt nhanh" if compact else "💡 Nhận xét phân tích tự động"
    cls = "dacs-insight-card is-compact" if compact else "dacs-insight-card"
    items = "".join(f"<li>{_esc(b)}</li>" for b in bullets)
    return (
        f'<div class="{cls}">'
        '<div class="dacs-insight-header">'
        f'<span class="dacs-insight-title">{_esc(title)}</span>'
        f'{src_badge}'
        '</div>'
        f'<ul class="dacs-insight-list">{items}</ul>'
        '</div>'
    )


def _schema_card_html(table: dict[str, Any], table_counts: dict[str, int]) -> str:
    name = table["name"]
    is_fact = table.get("kind") == "FACT"
    cls = "dacs-schema-card is-fact" if is_fact else "dacs-schema-card"
    badge_cls = "dacs-badge--primary" if is_fact else "dacs-badge--slate"
    row_count = table_counts.get(name)
    rows_txt = f"{row_count:,} dòng".replace(",", ".") if row_count is not None else "—"
    rels = table.get("relationships", [])
    rel_badge = f" · 🔗 {len(rels)} FK" if rels else ""
    return (
        f'<div class="{cls}">'
        '<div class="dacs-schema-head">'
        f'<span class="dacs-schema-name">{_esc(name)}</span>'
        f'<span class="dacs-badge {badge_cls}">{_esc(table.get("kind", ""))}</span>'
        '</div>'
        f'<div class="dacs-schema-desc">{_esc(table.get("description", ""))}</div>'
        '<div class="dacs-schema-meta">'
        f'<span>📏 {table.get("column_count", 0)} cột</span>'
        f'<span>· 📦 {_esc(rows_txt)}{_esc(rel_badge)}</span>'
        '</div>'
        '</div>'
    )


def star_schema_html(
    schema_summary: list[dict[str, Any]], table_counts: dict[str, int]
) -> str:
    """Sơ đồ trực quan bảng Fact ở trên và lưới các bảng Dimension bên dưới."""
    fact_cards = "".join(
        _schema_card_html(t, table_counts)
        for t in schema_summary
        if t.get("kind") == "FACT"
    )
    dim_cards = "".join(
        _schema_card_html(t, table_counts)
        for t in schema_summary
        if t.get("kind") != "FACT"
    )
    return (
        '<div class="dacs-schema-wrap">'
        f'{fact_cards}'
        f'<div class="dacs-schema-grid">{dim_cards}</div>'
        '</div>'
    )


def guardrails_grid_html(rules: list[tuple[str, str]]) -> str:
    """Lưới các thẻ quy tắc bảo mật SQL Guardrails."""
    cards = "".join(
        '<div class="dacs-guard-card">'
        f'<div class="dacs-guard-title">✓ {_esc(title)}</div>'
        f'<div class="dacs-guard-desc">{_esc(desc)}</div>'
        '</div>'
        for title, desc in rules
    )
    return f'<div class="dacs-guard-grid">{cards}</div>'
