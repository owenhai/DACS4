"""Lưu trữ bền vững lịch sử hỏi đáp & phiên làm việc (MySQL 8.0 / SQLite fallback).

Tách biệt hoàn toàn khỏi kho dữ liệu phân tích DuckDB (``olist_analytics.duckdb``)
để kết nối đọc DuckDB không bị xung đột khóa file trên Windows và giữ nguyên
lược đồ Star Schema 6 bảng.

Cơ chế chọn backend (khi không truyền ``db_path`` tường minh):
- Nếu biến môi trường ``HISTORY_BACKEND=sqlite`` -> luôn dùng SQLite.
- Nếu ``MYSQL_HOST`` được cấu hình (hoặc ``HISTORY_BACKEND=mysql``) -> ưu tiên
  kết nối MySQL 8.0; nếu kết nối/truy vấn gặp lỗi thì ghi nhận lý do (đã ẩn
  mật khẩu) và tự động fallback êm sang SQLite để ứng dụng luôn ổn định.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.models.insight_generator import InsightResult
from src.models.text_to_sql import QueryResult
from src.visualization.chart_classifier import ChartSpec, ChartType
from src.visualization.chart_generator import build_chart

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HISTORY_DB_ENV_VAR = "DACS4_HISTORY_DB_PATH"
HISTORY_BACKEND_ENV_VAR = "HISTORY_BACKEND"
DEFAULT_HISTORY_DB_PATH = _PROJECT_ROOT / "data" / "database" / "query_history.db"

_VALID_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")

_SQLITE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    model_name TEXT NOT NULL DEFAULT '',
    question TEXT NOT NULL,
    generated_sql TEXT NOT NULL DEFAULT '',
    success INTEGER NOT NULL DEFAULT 0,
    error_type TEXT,
    error_message TEXT,
    execution_time_ms REAL NOT NULL DEFAULT 0.0,
    correction_attempts INTEGER NOT NULL DEFAULT 0,
    correction_history_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    timings_ms_json TEXT NOT NULL DEFAULT '{}',
    chart_type TEXT,
    chart_spec_json TEXT,
    dataframe_json TEXT,
    insights_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_query_history_id ON query_history (id DESC);
"""

_MYSQL_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS query_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,
    timestamp VARCHAR(16) NOT NULL,
    model_name VARCHAR(100) NOT NULL DEFAULT '',
    question TEXT NOT NULL,
    generated_sql MEDIUMTEXT NOT NULL,
    success TINYINT(1) NOT NULL DEFAULT 0,
    error_type VARCHAR(64) NULL,
    error_message TEXT NULL,
    execution_time_ms DOUBLE NOT NULL DEFAULT 0.0,
    correction_attempts INT NOT NULL DEFAULT 0,
    correction_history_json MEDIUMTEXT NOT NULL,
    warnings_json MEDIUMTEXT NOT NULL,
    timings_ms_json TEXT NOT NULL,
    chart_type VARCHAR(64) NULL,
    chart_spec_json MEDIUMTEXT NULL,
    dataframe_json LONGTEXT NULL,
    insights_json MEDIUMTEXT NULL,
    INDEX idx_query_history_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

_mysql_schema_ready_key: tuple[str, int, str, str] | None = None
_last_fallback_reason: str | None = None


def _sanitize_error(err: BaseException | str, cfg: dict[str, Any] | None = None) -> str:
    """Loại bỏ mật khẩu MySQL (nếu có) trước khi ghi log hoặc hiển thị."""
    msg = str(err or "")
    secrets = []
    if cfg and cfg.get("password"):
        secrets.append(str(cfg["password"]))
    env_pw = os.getenv("MYSQL_PASSWORD", "")
    if env_pw:
        secrets.append(env_pw)
    for secret in secrets:
        if secret:
            msg = msg.replace(secret, "***")
    return msg.strip() or "Lỗi không xác định"


def get_mysql_config() -> dict[str, Any] | None:
    """Đọc cấu hình MySQL từ biến môi trường; trả về None nếu dùng SQLite."""
    backend = (os.getenv(HISTORY_BACKEND_ENV_VAR, "auto") or "auto").strip().lower()
    if backend == "sqlite":
        return None

    host = os.getenv("MYSQL_HOST", "").strip()
    if not host and backend != "mysql":
        return None

    port_raw = os.getenv("MYSQL_PORT", "3306").strip()
    try:
        port = int(port_raw) if port_raw else 3306
    except ValueError:
        port = 3306

    return {
        "host": host or "127.0.0.1",
        "port": port,
        "user": os.getenv("MYSQL_USER", "root").strip() or "root",
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "dacs4_insights").strip() or "dacs4_insights",
    }


def _validate_mysql_db_name(db_name: str) -> str:
    if not _VALID_DB_NAME_RE.fullmatch(db_name):
        raise ValueError(f"Tên MySQL database không hợp lệ: {db_name}")
    return db_name


def _connect_mysql(cfg: dict[str, Any], database: str | None = None):
    import pymysql
    import pymysql.cursors

    kwargs: dict[str, Any] = {
        "host": cfg["host"],
        "port": int(cfg["port"]),
        "user": cfg["user"],
        "password": cfg["password"],
        "charset": "utf8mb4",
        "connect_timeout": 3,
        "read_timeout": 5,
        "write_timeout": 5,
        "cursorclass": pymysql.cursors.DictCursor,
    }
    if database is not None:
        kwargs["database"] = database
    return pymysql.connect(**kwargs)


def _init_mysql_db(cfg: dict[str, Any]) -> None:
    """Tạo database và bảng ``query_history`` trên MySQL nếu chưa có."""
    global _mysql_schema_ready_key
    db_name = _validate_mysql_db_name(cfg["database"])
    key = (cfg["host"], int(cfg["port"]), cfg["user"], db_name)
    if _mysql_schema_ready_key == key:
        return

    conn = _connect_mysql(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.execute(f"USE `{db_name}`")
            cur.execute(_MYSQL_CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()
    _mysql_schema_ready_key = key


def _handle_mysql_error(exc: BaseException, cfg: dict[str, Any], action: str) -> str:
    global _mysql_schema_ready_key, _last_fallback_reason
    _mysql_schema_ready_key = None
    reason = _sanitize_error(exc, cfg)
    _last_fallback_reason = reason
    logger.warning(
        "MySQL %s thất bại (%s); tự động fallback sang SQLite.", action, reason
    )
    return reason


def resolve_history_db_path(db_path: str | Path | None = None) -> Path:
    """Xác định đường dẫn file SQLite lưu lịch sử hỏi đáp."""
    if db_path is not None:
        return Path(db_path)
    env_val = os.getenv(HISTORY_DB_ENV_VAR, "").strip()
    if env_val:
        return Path(env_val)
    return DEFAULT_HISTORY_DB_PATH


def init_history_db(db_path: str | Path | None = None) -> Path:
    """Khởi tạo thư mục và bảng ``query_history`` SQLite nếu chưa tồn tại."""
    resolved = resolve_history_db_path(db_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved), timeout=10.0)
    try:
        conn.executescript(_SQLITE_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return resolved


def _safe_json_dumps(value: Any, fallback: str) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return fallback


def _safe_json_loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return fallback


def _serialize_dataframe(df: pd.DataFrame | None) -> str | None:
    if df is None:
        return None
    try:
        return df.to_json(orient="split", date_format="iso", default_handler=str)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Không thể tuần tự hóa DataFrame: %s", exc)
        return None


def _deserialize_dataframe(raw: str | None) -> pd.DataFrame | None:
    if not raw:
        return None
    try:
        return pd.read_json(io.StringIO(raw), orient="split")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Không thể khôi phục DataFrame từ lịch sử: %s", exc)
        return None


def _serialize_chart_spec(spec: ChartSpec | Any | None) -> str | None:
    if spec is None:
        return None
    ct = getattr(spec, "chart_type", None)
    ct_val = ct.value if hasattr(ct, "value") else ct
    if not ct_val:
        return None
    payload = {
        "chart_type": str(ct_val),
        "x": getattr(spec, "x", None),
        "y": getattr(spec, "y", None),
        "color": getattr(spec, "color", None),
        "hover": list(getattr(spec, "hover", []) or []),
        "lat": getattr(spec, "lat", None),
        "lon": getattr(spec, "lon", None),
        "reason": getattr(spec, "reason", "") or "",
        "roles": dict(getattr(spec, "roles", {}) or {}),
    }
    return _safe_json_dumps(payload, "{}")


def _deserialize_chart_spec(raw: str | None) -> ChartSpec | None:
    data = _safe_json_loads(raw, None)
    if not isinstance(data, dict) or not data.get("chart_type"):
        return None
    try:
        ct = ChartType(data["chart_type"])
    except ValueError:
        return None
    return ChartSpec(
        chart_type=ct,
        x=data.get("x"),
        y=data.get("y"),
        color=data.get("color"),
        hover=list(data.get("hover") or []),
        lat=data.get("lat"),
        lon=data.get("lon"),
        reason=str(data.get("reason") or ""),
        roles=dict(data.get("roles") or {}),
    )


def _serialize_insights(insights: InsightResult | Any | None) -> str | None:
    if insights is None:
        return None
    payload = {
        "bullets": list(getattr(insights, "bullets", []) or []),
        "statistics": dict(getattr(insights, "statistics", {}) or {}),
        "source": str(getattr(insights, "source", "rule") or "rule"),
        "error": getattr(insights, "error", None),
    }
    return _safe_json_dumps(payload, "{}")


def _deserialize_insights(raw: str | None) -> InsightResult | None:
    data = _safe_json_loads(raw, None)
    if not isinstance(data, dict) or "bullets" not in data:
        return None
    return InsightResult(
        bullets=list(data.get("bullets") or []),
        statistics=dict(data.get("statistics") or {}),
        source=str(data.get("source") or "rule"),
        error=data.get("error"),
    )


def _prepare_entry_record(entry: dict[str, Any], model_name: str = "") -> tuple[Any, ...]:
    """Chuẩn bị tuple giá trị thống nhất để ghi vào SQLite hoặc MySQL."""
    res = entry.get("result")
    now = datetime.now()
    created_at = str(entry.get("created_at") or now.strftime("%Y-%m-%d %H:%M:%S"))
    timestamp = str(entry.get("timestamp") or now.strftime("%H:%M:%S"))
    question = str(entry.get("question") or getattr(res, "question", ""))
    generated_sql = str(getattr(res, "generated_sql", "") or "")
    success = 1 if bool(entry.get("success", getattr(res, "success", False))) else 0
    error_type = getattr(res, "error_type", None)
    error_message = getattr(res, "error_message", None)
    exec_ms = getattr(res, "execution_time_ms", None)
    if exec_ms is None:
        exec_ms = float(entry.get("total_s", 0.0) or 0.0) * 1000.0
    correction_attempts = int(getattr(res, "correction_attempts", 0) or 0)
    correction_history_json = _safe_json_dumps(
        getattr(res, "correction_history", []) or [], "[]"
    )
    warnings_json = _safe_json_dumps(getattr(res, "warnings", []) or [], "[]")
    timings_ms_json = _safe_json_dumps(getattr(res, "timings_ms", {}) or {}, "{}")

    chart_spec = getattr(res, "chart_spec", None)
    chart_type = entry.get("chart_type")
    if chart_type is None and chart_spec is not None:
        ct = getattr(chart_spec, "chart_type", None)
        chart_type = ct.value if hasattr(ct, "value") else ct

    chart_spec_json = _serialize_chart_spec(chart_spec)
    dataframe_json = _serialize_dataframe(getattr(res, "dataframe", None))
    insights_json = _serialize_insights(getattr(res, "insights", None))

    return (
        created_at,
        timestamp,
        model_name,
        question,
        generated_sql,
        success,
        error_type,
        error_message,
        float(exec_ms or 0.0),
        correction_attempts,
        correction_history_json,
        warnings_json,
        timings_ms_json,
        chart_type,
        chart_spec_json,
        dataframe_json,
        insights_json,
    )


def _row_to_entry(row: Any) -> dict[str, Any]:
    """Khôi phục bản ghi ``entry`` (kèm ``QueryResult`` và Plotly chart) từ một dòng DB."""
    df = _deserialize_dataframe(row["dataframe_json"])
    spec = _deserialize_chart_spec(row["chart_spec_json"])
    insights = _deserialize_insights(row["insights_json"])
    success = bool(row["success"])

    chart = None
    if success and df is not None and not df.empty and spec is not None:
        try:
            chart = build_chart(df, spec, row["question"])
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Không thể tạo lại biểu đồ cho bản ghi #%s: %s", row["id"], exc
            )

    qr = QueryResult(
        question=row["question"],
        generated_sql=row["generated_sql"] or "",
        dataframe=df,
        success=success,
        error_message=row["error_message"],
        execution_time_ms=float(row["execution_time_ms"] or 0.0),
        correction_attempts=int(row["correction_attempts"] or 0),
        correction_history=_safe_json_loads(row["correction_history_json"], []),
        error_type=row["error_type"],
        warnings=_safe_json_loads(row["warnings_json"], []),
        chart=chart,
        chart_spec=spec,
        insights=insights,
        timings_ms=_safe_json_loads(row["timings_ms_json"], {}),
    )
    return {
        "id": int(row["id"]),
        "created_at": row["created_at"],
        "timestamp": row["timestamp"],
        "model_name": row["model_name"] or "",
        "question": row["question"],
        "success": success,
        "chart_type": row["chart_type"],
        "total_s": round(float(row["execution_time_ms"] or 0.0) / 1000.0, 2),
        "result": qr,
    }


def save_history_entry(
    entry: dict[str, Any],
    model_name: str = "",
    db_path: str | Path | None = None,
) -> int:
    """Lưu một bản ghi lịch sử hỏi đáp (MySQL ưu tiên nếu bật, fallback SQLite)."""
    global _last_fallback_reason
    record = _prepare_entry_record(entry, model_name=model_name)
    created_at = record[0]

    cfg = None if db_path is not None else get_mysql_config()
    if cfg is not None:
        try:
            _init_mysql_db(cfg)
            conn = _connect_mysql(cfg, database=cfg["database"])
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO query_history (
                            created_at, timestamp, model_name, question, generated_sql,
                            success, error_type, error_message, execution_time_ms,
                            correction_attempts, correction_history_json, warnings_json,
                            timings_ms_json, chart_type, chart_spec_json, dataframe_json,
                            insights_json
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        record,
                    )
                    row_id = int(cur.lastrowid)
                conn.commit()
            finally:
                conn.close()
            _last_fallback_reason = None
            entry["id"] = row_id
            entry["created_at"] = created_at
            entry["model_name"] = model_name
            return row_id
        except Exception as exc:  # noqa: BLE001
            _handle_mysql_error(exc, cfg, "lưu lịch sử")

    resolved = init_history_db(db_path)
    conn = sqlite3.connect(str(resolved), timeout=10.0)
    try:
        cursor = conn.execute(
            """
            INSERT INTO query_history (
                created_at, timestamp, model_name, question, generated_sql,
                success, error_type, error_message, execution_time_ms,
                correction_attempts, correction_history_json, warnings_json,
                timings_ms_json, chart_type, chart_spec_json, dataframe_json,
                insights_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            record,
        )
        conn.commit()
        row_id = int(cursor.lastrowid)
    finally:
        conn.close()

    entry["id"] = row_id
    entry["created_at"] = created_at
    entry["model_name"] = model_name
    return row_id


def load_history(
    limit: int = 50,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Đọc các bản ghi lịch sử gần nhất theo thứ tự cũ → mới."""
    global _last_fallback_reason
    safe_limit = max(1, int(limit))

    cfg = None if db_path is not None else get_mysql_config()
    if cfg is not None:
        try:
            _init_mysql_db(cfg)
            conn = _connect_mysql(cfg, database=cfg["database"])
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM query_history ORDER BY id DESC LIMIT %s",
                        (safe_limit,),
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()
            _last_fallback_reason = None
            return [_row_to_entry(row) for row in reversed(rows)]
        except Exception as exc:  # noqa: BLE001
            _handle_mysql_error(exc, cfg, "nạp lịch sử")

    resolved = init_history_db(db_path)
    conn = sqlite3.connect(str(resolved), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM query_history ORDER BY id DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_entry(row) for row in reversed(rows)]


def delete_history_entry(
    entry_id: int,
    db_path: str | Path | None = None,
) -> bool:
    """Xóa một bản ghi lịch sử theo ``id``."""
    global _last_fallback_reason
    cfg = None if db_path is not None else get_mysql_config()
    if cfg is not None:
        try:
            _init_mysql_db(cfg)
            conn = _connect_mysql(cfg, database=cfg["database"])
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM query_history WHERE id = %s",
                        (int(entry_id),),
                    )
                    deleted = cur.rowcount > 0
                conn.commit()
            finally:
                conn.close()
            _last_fallback_reason = None
            return deleted
        except Exception as exc:  # noqa: BLE001
            _handle_mysql_error(exc, cfg, "xóa bản ghi")

    resolved = resolve_history_db_path(db_path)
    if not resolved.exists():
        return False
    conn = sqlite3.connect(str(resolved), timeout=10.0)
    try:
        cursor = conn.execute(
            "DELETE FROM query_history WHERE id = ?",
            (int(entry_id),),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def clear_history(db_path: str | Path | None = None) -> int:
    """Xóa toàn bộ lịch sử hỏi đáp khỏi backend lưu trữ, trả về số dòng đã xóa."""
    global _last_fallback_reason
    cfg = None if db_path is not None else get_mysql_config()
    if cfg is not None:
        try:
            _init_mysql_db(cfg)
            conn = _connect_mysql(cfg, database=cfg["database"])
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM query_history")
                    count = int(cur.rowcount or 0)
                conn.commit()
            finally:
                conn.close()
            _last_fallback_reason = None
            return count
        except Exception as exc:  # noqa: BLE001
            _handle_mysql_error(exc, cfg, "xóa toàn bộ lịch sử")

    resolved = init_history_db(db_path)
    conn = sqlite3.connect(str(resolved), timeout=10.0)
    try:
        cursor = conn.execute("DELETE FROM query_history")
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def get_history_stats(db_path: str | Path | None = None) -> dict[str, Any]:
    """Trả về thống kê kích thước, số bản ghi và trạng thái backend đang dùng."""
    global _last_fallback_reason
    fallback_used = False
    fallback_reason: str | None = None

    cfg = None if db_path is not None else get_mysql_config()
    if cfg is not None:
        try:
            _init_mysql_db(cfg)
            conn = _connect_mysql(cfg, database=cfg["database"])
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) AS total_entries, "
                        "COALESCE(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END), 0) AS success_count "
                        "FROM query_history"
                    )
                    row = cur.fetchone() or {}
                    cur.execute(
                        "SELECT ROUND(COALESCE(SUM(data_length + index_length), 0) / 1024.0, 1) AS size_kb "
                        "FROM information_schema.tables "
                        "WHERE table_schema = %s AND table_name = 'query_history'",
                        (cfg["database"],),
                    )
                    size_row = cur.fetchone() or {}
            finally:
                conn.close()
            _last_fallback_reason = None
            return {
                "db_path": f"{cfg['host']}:{cfg['port']} / {cfg['database']}",
                "exists": True,
                "total_entries": int(row.get("total_entries") or 0),
                "success_count": int(row.get("success_count") or 0),
                "file_size_kb": float(size_row.get("size_kb") or 0.0),
                "backend": "mysql",
                "fallback_used": False,
                "fallback_reason": None,
            }
        except Exception as exc:  # noqa: BLE001
            fallback_reason = _handle_mysql_error(exc, cfg, "đọc thống kê")
            fallback_used = True
    elif db_path is None:
        _last_fallback_reason = None

    resolved = resolve_history_db_path(db_path)
    if not resolved.exists():
        return {
            "db_path": str(resolved),
            "exists": False,
            "total_entries": 0,
            "success_count": 0,
            "file_size_kb": 0.0,
            "backend": "sqlite",
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
        }

    init_history_db(resolved)
    conn = sqlite3.connect(str(resolved), timeout=10.0)
    try:
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END), 0) "
            "FROM query_history"
        ).fetchone()
    finally:
        conn.close()

    total_entries = int(row[0] or 0) if row else 0
    success_count = int(row[1] or 0) if row else 0
    size_kb = round(resolved.stat().st_size / 1024.0, 1)
    return {
        "db_path": str(resolved),
        "exists": True,
        "total_entries": total_entries,
        "success_count": success_count,
        "file_size_kb": size_kb,
        "backend": "sqlite",
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(_PROJECT_ROOT / ".env", override=False)
    stats = get_history_stats()
    entries = load_history(limit=5)

    backend_label = stats.get("backend", "sqlite").upper()
    if stats.get("fallback_used"):
        backend_label += " (fallback)"

    print("=" * 60)
    print("DACS4 - KIEM TRA CSDL LICH SU HOI DAP")
    print("=" * 60)
    print(f"Backend : {backend_label}")
    print(f"Target  : {stats['db_path']}")
    print(f"Tong log: {stats['total_entries']} (thanh cong: {stats['success_count']}, {stats['file_size_kb']} KB)")
    if stats.get("fallback_reason"):
        print(f"Fallback: {stats['fallback_reason']}")
    print("-" * 60)
    if not entries:
        print("Chua co ban ghi nao.")
    else:
        for item in reversed(entries):
            status_txt = "OK" if item["success"] else "ERR"
            print(
                f"#{item['id']} [{item['created_at']}] [{status_txt}] "
                f"({item['total_s']}s) {item['question']}"
            )
