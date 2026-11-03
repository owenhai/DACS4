# DACS4 – Automated Data Insights Engine

## Overview
Automated Data Insights Engine (DACS4) combines **DuckDB** star‑schema analytics with **Gemini Flash** LLM to provide a natural‑language → SQL pipeline. Users ask questions in Vietnamese or English, the system generates SQL, executes it on DuckDB, and returns results, visualizations, and insights.

---

## Project Proposal (Excerpt)

**Tên đề tài:** Nghiên cứu và xây dựng hệ thống phân tích dữ liệu thông minh kết hợp Text‑to‑SQL và LLM.

- **Mục tiêu:**
  - Xây dựng Star Schema cho bộ dữ liệu Olist.
  - Tích hợp Gemini Flash để sinh SQL qua prompt engineering.
  - Phát triển SQL Guardrails và Self‑Correction Loop.
  - Tự động tạo biểu đồ và insight bằng Plotly & LLM.
  - Đánh giá độ chính xác và latency.

Full proposal is in `project_proposal.md`.

---

## Progress Tracker

```
# 📊 DACS4 - TIẾN ĐỘ DỰ ÁN

| Tuần | Nội dung chính | Trạng thái | Hoàn thành |
|:----:|----------------|:----------:|:----------:|
| 1 | Thu thập & xử lý dữ liệu, Star Schema & DuckDB | 🟢 Hoàn thành | ██████████ 100% |
| 2 | Tích hợp Gemini Flash, Prompt Engineering, Text‑to‑SQL | 🟢 Hoàn thành | ██████████ 100% |
| 3 | SQL Guardrails & Self‑Correction Loop | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 4 | Auto Visualization & Insight Generation | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 5 | Giao diện Streamlit | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 6 | Kiểm thử & Đánh giá hiệu năng | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 7 | Viết báo cáo đồ án | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
| 8 | Đóng gói, Slide & Video demo | ⚪ Chưa bắt đầu | ░░░░░░░░░░ 0% |
```

See `PROGRESS_TRACKER.md` for detailed checklist.

---

## Repository Structure

```
DACS4/
├─ app.py                # Streamlit entry (to be added)
├─ config.py
├─ requirements.txt
├─ README.md             # Short overview (this file)
├─ COMBINED_README.md    # Full documentation (generated)
├─ .env.example
├─ data/
│   ├─ raw/              # Original CSV files
│   └─ database/olist_analytics.duckdb
├─ src/
│   ├─ data/            # ETL, schema, EDA scripts
│   └─ models/          # llm_client, prompt_templates, text_to_sql
├─ docs/                # Detailed docs (STAR_SCHEMA.md, WEEK1_SUMMARY.md)
├─ tests/               # Unit tests
└─ results/             # Benchmark results (future)
```

---

## Getting Started

```powershell
cd "D:\Project _Lab_Doc\DA\DACS4"
python -m pip install -r requirements.txt
```

Create a `.env` file with your Gemini API key:

```
GOOGLE_API_KEY=your_google_gemini_api_key
```

Run the demo pipeline:

```powershell
python -m src.models.text_to_sql
```

---

## Further Documentation

- **Star Schema details:** `docs/STAR_SCHEMA.md`
- **Week 1 summary:** `docs/WEEK1_SUMMARY.md`
- **Full proposal:** `project_proposal.md`

---

*This combined README was generated to consolidate all project markdown files into a single reference document.*