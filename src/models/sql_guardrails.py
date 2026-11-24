"""SQL Guardrails: kiểm duyệt an toàn câu SQL trước khi thực thi trên DuckDB.

Các lớp bảo vệ (theo thứ tự kiểm tra):
1. SQL rỗng / quá dài
2. Loại bỏ comment (chặn comment injection ``--`` và ``/* */``)
3. Chặn nhiều câu lệnh (stacked queries: ``SELECT 1; DROP TABLE x``)
4. Whitelist: chỉ cho phép câu lệnh ``SELECT`` (kể cả ``WITH ... SELECT``)
5. Blacklist từ khóa nguy hiểm (DROP, DELETE, UPDATE, INSERT, ALTER, ...)
6. Chặn các hàm đọc file / hệ thống của DuckDB (read_csv, glob, ...)
7. Giới hạn độ phức tạp (số JOIN, độ sâu subquery)
8. Kiểm tra tên bảng và cột (``alias.column``) có trong schema

Lỗi được chia thành 2 nhóm:
- ``security``: vi phạm bảo mật -> KHÔNG gửi cho LLM sửa, dừng ngay.
- ``unknown_table`` / ``unknown_column`` / ``complexity`` / ``syntax``:
  lỗi có thể sửa -> Self-Correction Loop sẽ gửi phản hồi cho LLM.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import sqlparse
from sqlparse import tokens as T

from src.data.schema_metadata import get_schema_metadata

logger = logging.getLogger(__name__)


# ===========================================================================
# Cấu hình
# ===========================================================================

#: Từ khóa bị cấm (DML/DDL/hệ thống). Không chứa REPLACE vì đó cũng là hàm chuỗi.
BLACKLISTED_KEYWORDS: frozenset[str] = frozenset({
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE",
    "EXEC", "EXECUTE", "MERGE", "GRANT", "REVOKE", "ATTACH", "DETACH",
    "COPY", "PRAGMA", "INSTALL", "LOAD", "EXPORT", "IMPORT", "CALL",
    "VACUUM", "CHECKPOINT", "UPSERT",
})

#: Hàm của DuckDB có thể đọc file / truy cập hệ thống -> cấm.
BLOCKED_FUNCTIONS: frozenset[str] = frozenset({
    "read_csv", "read_csv_auto", "read_parquet", "parquet_scan",
    "read_json", "read_json_auto", "read_json_objects", "read_ndjson",
    "read_text", "read_blob", "glob", "csv_scan", "json_scan", "sniff_csv",
    "sqlite_scan", "postgres_scan", "mysql_scan", "iceberg_scan",
    "delta_scan", "getenv", "current_setting",
})

#: Hàm bảng (table function) được phép dùng sau FROM.
ALLOWED_TABLE_FUNCTIONS: frozenset[str] = frozenset({
    "generate_series", "range", "unnest",
})

ERROR_SECURITY = "security"
ERROR_SYNTAX = "syntax"
ERROR_UNKNOWN_TABLE = "unknown_table"
ERROR_UNKNOWN_COLUMN = "unknown_column"
ERROR_COMPLEXITY = "complexity"

_STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")
# Các hàm có cú pháp "... FROM ..." bên trong ngoặc, cần loại trước khi tìm bảng
_FUNC_WITH_FROM_RE = re.compile(
    r"\b(?:EXTRACT|TRIM|SUBSTRING|POSITION|OVERLAY)\s*\([^()]*\)", re.IGNORECASE
)
_CTE_NAME_RE = re.compile(
    r"(?:\bWITH\s+(?:RECURSIVE\s+)?|,\s*)([A-Za-z_]\w*)\s+AS\s*(?:NOT\s+)?(?:MATERIALIZED\s+)?\(",
    re.IGNORECASE,
)
_TABLE_REF_RE = re.compile(
    r"\b(FROM|JOIN)\s+(\"?[A-Za-z_][\w]*\"?(?:\.\"?[A-Za-z_][\w]*\"?)?)\s*(\()?"
    r"(?:\s*(?:AS\s+)?(\"?[A-Za-z_]\w*\"?))?",
    re.IGNORECASE,
)
_QUALIFIED_COL_RE = re.compile(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b(?!\s*\()")
_JOIN_RE = re.compile(r"\bJOIN\b", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)(\s+OFFSET\s+\d+)?\s*$", re.IGNORECASE)

# Từ khóa không thể là alias của bảng
_NON_ALIAS_WORDS = frozenset({
    "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET", "ON", "USING",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "NATURAL",
    "UNION", "EXCEPT", "INTERSECT", "WINDOW", "QUALIFY", "SELECT", "AS",
    "LATERAL", "POSITIONAL", "ASOF", "ANTI", "SEMI",
})


# ===========================================================================
# Kết quả
# ===========================================================================

@dataclass
class ValidationResult:
    """Kết quả kiểm duyệt SQL.

    Attributes:
        is_valid: SQL có an toàn và hợp lệ để thực thi không.
        error_message: Mô tả lỗi (None nếu hợp lệ).
        sanitized_sql: SQL đã làm sạch (bỏ comment, thêm LIMIT) - dùng để thực thi.
        error_type: Loại lỗi (security, syntax, unknown_table, ...).
        warnings: Cảnh báo không chặn (ví dụ: đã bỏ comment, đã thêm LIMIT).
    """

    is_valid: bool
    error_message: str | None = None
    sanitized_sql: str = ""
    error_type: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def is_security_violation(self) -> bool:
        """Lỗi bảo mật - không được gửi cho LLM sửa."""
        return self.error_type == ERROR_SECURITY


# ===========================================================================
# Guardrails
# ===========================================================================

class SQLGuardrails:
    """Bộ kiểm duyệt SQL dựa trên ``sqlparse`` và schema metadata.

    Attributes:
        max_joins: Số JOIN tối đa cho phép.
        max_subquery_depth: Độ sâu subquery lồng nhau tối đa.
        default_limit: LIMIT tự thêm khi câu SQL không có LIMIT.
        max_limit: LIMIT tối đa; LIMIT lớn hơn sẽ bị giảm xuống.
        max_length: Độ dài SQL tối đa (ký tự).
    """

    def __init__(
        self,
        schema: dict | None = None,
        max_joins: int = 8,
        max_subquery_depth: int = 3,
        default_limit: int = 1000,
        max_limit: int = 10000,
        max_length: int = 5000,
        check_columns: bool = True,
    ) -> None:
        schema = schema if schema is not None else get_schema_metadata()
        # {table_lower: {col_lower, ...}}
        self.tables: dict[str, set[str]] = {
            name.lower(): {c.lower() for c in info.get("columns", {})}
            for name, info in schema.items()
        }
        self.max_joins = max_joins
        self.max_subquery_depth = max_subquery_depth
        self.default_limit = default_limit
        self.max_limit = max_limit
        self.max_length = max_length
        self.check_columns = check_columns

    # ------------------------------------------------------------------
    # API chính
    # ------------------------------------------------------------------

    def validate_sql(self, sql: str) -> ValidationResult:
        """Kiểm duyệt một câu SQL.

        Args:
            sql: Câu SQL do LLM sinh ra.

        Returns:
            ValidationResult với ``sanitized_sql`` sẵn sàng thực thi nếu hợp lệ.
        """
        warnings: list[str] = []

        # 1. Rỗng / quá dài
        if not sql or not sql.strip():
            return self._fail("SQL rỗng.", ERROR_SYNTAX)
        if len(sql) > self.max_length:
            return self._fail(
                f"SQL quá dài ({len(sql)} > {self.max_length} ký tự).",
                ERROR_COMPLEXITY,
            )

        # 2. Loại bỏ comment (comment injection)
        no_comments = sqlparse.format(sql, strip_comments=True).strip()
        if self._has_comments(sql):
            warnings.append("Đã loại bỏ comment trong SQL.")
        if not no_comments:
            return self._fail("SQL chỉ chứa comment.", ERROR_SYNTAX)

        # 3. Nhiều câu lệnh
        statements = [s for s in sqlparse.split(no_comments) if s.strip().strip(";").strip()]
        if len(statements) != 1:
            return self._fail(
                f"Chỉ cho phép 1 câu lệnh, phát hiện {len(statements)} câu lệnh.",
                ERROR_SECURITY,
            )
        statement_sql = statements[0].strip().rstrip(";").strip()
        parsed = sqlparse.parse(statement_sql)[0]

        # 5. Blacklist (kiểm tra trước whitelist để báo lỗi cụ thể hơn)
        forbidden = self._find_forbidden_keywords(parsed)
        if forbidden:
            return self._fail(
                f"Phát hiện từ khóa bị cấm: {', '.join(sorted(forbidden))}. "
                "Hệ thống chỉ cho phép truy vấn đọc dữ liệu (SELECT).",
                ERROR_SECURITY,
            )

        # 4. Whitelist SELECT
        stmt_type = parsed.get_type()
        if stmt_type != "SELECT":
            # sqlparse returns UNKNOWN for malformed SELECT statements such
            # as "SELEC ...". Treat those as fixable syntax errors so the
            # self-correction loop can ask the LLM for a corrected query.
            first = parsed.token_first(skip_cm=True, skip_ws=True)
            first_word = ""
            if first is not None:
                first_word = first.value.split()[0].upper() if first.value.split() else ""
            if stmt_type == "UNKNOWN" and first_word:
                return self._fail(
                    f"Cú pháp SQL không hợp lệ (phát hiện: {first_word}).",
                    ERROR_SYNTAX,
                )
            return self._fail(
                f"Chỉ cho phép câu lệnh SELECT (phát hiện: {stmt_type}).",
                ERROR_SECURITY,
            )

        scrubbed = self._strip_literals(statement_sql)

        # 6. Hàm đọc file / hệ thống
        blocked = self._find_blocked_functions(scrubbed)
        if blocked:
            return self._fail(
                f"Không được dùng hàm truy cập file/hệ thống: {', '.join(sorted(blocked))}.",
                ERROR_SECURITY,
            )

        # 7. Độ phức tạp
        join_count = len(_JOIN_RE.findall(scrubbed))
        if join_count > self.max_joins:
            return self._fail(
                f"Quá nhiều JOIN ({join_count} > {self.max_joins}). Hãy đơn giản hóa truy vấn.",
                ERROR_COMPLEXITY,
            )
        depth = self._subquery_depth(scrubbed)
        if depth > self.max_subquery_depth:
            return self._fail(
                f"Subquery lồng quá sâu ({depth} > {self.max_subquery_depth}). "
                "Hãy dùng CTE (WITH) để đơn giản hóa.",
                ERROR_COMPLEXITY,
            )

        # 8. Bảng & cột
        ref_error = self._check_references(scrubbed)
        if ref_error is not None:
            return ref_error

        sanitized, limit_warnings = self._apply_limit(statement_sql, scrubbed)
        warnings.extend(limit_warnings)

        return ValidationResult(
            is_valid=True,
            sanitized_sql=sanitized,
            warnings=warnings,
        )

    def sanitize_sql(self, sql: str) -> str:
        """Làm sạch SQL: bỏ comment, bỏ dấu ``;``, thêm/giới hạn LIMIT.

        Không kiểm tra bảo mật - dùng ``validate_sql`` trước khi thực thi.
        """
        cleaned = sqlparse.format(sql, strip_comments=True).strip().rstrip(";").strip()
        sanitized, _ = self._apply_limit(cleaned, self._strip_literals(cleaned))
        return sanitized

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fail(message: str, error_type: str) -> ValidationResult:
        logger.warning("SQL bị chặn [%s]: %s", error_type, message)
        return ValidationResult(is_valid=False, error_message=message, error_type=error_type)

    @staticmethod
    def _has_comments(sql: str) -> bool:
        for stmt in sqlparse.parse(sql):
            for tok in stmt.flatten():
                if tok.ttype in T.Comment:
                    return True
        return False

    @staticmethod
    def _strip_literals(sql: str) -> str:
        """Thay chuỗi '...' bằng '' để tránh phân tích nhầm nội dung chuỗi."""
        return _STRING_LITERAL_RE.sub("''", sql)

    @staticmethod
    def _find_forbidden_keywords(parsed: sqlparse.sql.Statement) -> set[str]:
        """Tìm từ khóa cấm ở dạng token Keyword (không tính nội dung chuỗi/tên cột).

        Ngoài ra, từ đầu tiên của câu lệnh nằm trong blacklist cũng bị chặn
        (sqlparse đôi khi nhận diện PRAGMA/EXEC là Name thay vì Keyword).
        """
        found: set[str] = set()
        for tok in parsed.flatten():
            if tok.ttype in T.Keyword and tok.value.upper() in BLACKLISTED_KEYWORDS:
                found.add(tok.value.upper())
        first = parsed.token_first(skip_cm=True, skip_ws=True)
        if first is not None:
            first_word = first.value.split()[0].upper() if first.value.split() else ""
            if first_word in BLACKLISTED_KEYWORDS:
                found.add(first_word)
        return found

    @staticmethod
    def _find_blocked_functions(scrubbed: str) -> set[str]:
        found = set()
        for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", scrubbed):
            name = match.group(1).lower()
            if name in BLOCKED_FUNCTIONS or name.startswith("duckdb_"):
                found.add(name)
        return found

    @staticmethod
    def _subquery_depth(scrubbed: str) -> int:
        """Độ sâu tối đa của các ngoặc chứa SELECT (subquery lồng nhau)."""
        stack: list[bool] = []
        max_depth = 0
        for i, ch in enumerate(scrubbed):
            if ch == "(":
                following = scrubbed[i + 1:i + 20].lstrip().upper()
                is_sub = following.startswith("SELECT") or following.startswith("WITH")
                stack.append(is_sub)
                max_depth = max(max_depth, sum(stack))
            elif ch == ")" and stack:
                stack.pop()
        return max_depth

    def _check_references(self, scrubbed: str) -> ValidationResult | None:
        """Kiểm tra bảng sau FROM/JOIN và cột dạng ``alias.column``."""
        text = scrubbed
        # Loại các hàm có FROM bên trong, lặp để xử lý lồng nhau đơn giản
        for _ in range(3):
            text = _FUNC_WITH_FROM_RE.sub("__fn__", text)

        cte_names = {m.group(1).lower() for m in _CTE_NAME_RE.finditer(text)}
        alias_map: dict[str, str] = {}  # alias/table -> table thật (lower)
        unknown: list[str] = []

        for match in _TABLE_REF_RE.finditer(text):
            raw_name, is_func, alias = match.group(2), match.group(3), match.group(4)
            name = raw_name.replace('"', "")
            if is_func:
                func = name.split(".")[-1].lower()
                if func not in ALLOWED_TABLE_FUNCTIONS:
                    return self._fail(
                        f"Không được dùng hàm bảng '{func}'.", ERROR_SECURITY
                    )
                continue
            parts = name.lower().split(".")
            if len(parts) == 2 and parts[0] not in ("main",):
                return self._fail(
                    f"Không được truy cập schema '{parts[0]}'. "
                    f"Các bảng hợp lệ: {', '.join(sorted(self.tables))}.",
                    ERROR_UNKNOWN_TABLE if parts[0] not in (
                        "information_schema", "pg_catalog", "system", "temp"
                    ) else ERROR_SECURITY,
                )
            table = parts[-1]
            if table in cte_names:
                continue
            if table not in self.tables:
                unknown.append(table)
                continue
            alias_map[table] = table
            if alias:
                alias_clean = alias.replace('"', "").lower()
                if alias_clean.upper() not in _NON_ALIAS_WORDS:
                    alias_map[alias_clean] = table

        if unknown:
            return self._fail(
                f"Bảng không tồn tại: {', '.join(sorted(set(unknown)))}. "
                f"Các bảng hợp lệ: {', '.join(sorted(self.tables))}.",
                ERROR_UNKNOWN_TABLE,
            )

        if self.check_columns:
            bad_cols: list[str] = []
            for m in _QUALIFIED_COL_RE.finditer(text):
                qualifier, column = m.group(1).lower(), m.group(2).lower()
                table = alias_map.get(qualifier)
                if table is None:
                    continue  # alias của CTE/subquery -> không kiểm tra
                if column not in self.tables[table]:
                    bad_cols.append(f"{qualifier}.{column} (bảng {table})")
            if bad_cols:
                first_table = alias_map.get(bad_cols[0].split(".")[0], "")
                hint = ""
                if first_table:
                    hint = f" Các cột của {first_table}: {', '.join(sorted(self.tables[first_table]))}."
                return self._fail(
                    f"Cột không tồn tại: {', '.join(dict.fromkeys(bad_cols))}.{hint}",
                    ERROR_UNKNOWN_COLUMN,
                )
        return None

    def _apply_limit(self, sql: str, scrubbed: str) -> tuple[str, list[str]]:
        """Thêm LIMIT mặc định hoặc giảm LIMIT quá lớn (chỉ ở cấp ngoài cùng)."""
        warnings: list[str] = []
        top_level = self._top_level_text(scrubbed)
        match = _LIMIT_RE.search(top_level)
        if match is None:
            if re.search(r"\bLIMIT\b", top_level, re.IGNORECASE):
                return sql, warnings  # LIMIT dạng biểu thức - giữ nguyên
            warnings.append(f"Đã thêm LIMIT {self.default_limit}.")
            return f"{sql}\nLIMIT {self.default_limit}", warnings

        value = int(match.group(1))
        if value > self.max_limit:
            warnings.append(f"Đã giảm LIMIT từ {value} xuống {self.max_limit}.")
            new_sql = re.sub(
                r"\bLIMIT\s+\d+(\s+OFFSET\s+\d+)?\s*$",
                lambda m: f"LIMIT {self.max_limit}{m.group(1) or ''}",
                sql,
                flags=re.IGNORECASE,
            )
            return new_sql, warnings
        return sql, warnings

    @staticmethod
    def _top_level_text(scrubbed: str) -> str:
        """Giữ lại phần text ở độ sâu ngoặc 0 (thay phần trong ngoặc bằng khoảng trắng)."""
        out = []
        depth = 0
        for ch in scrubbed:
            if ch == "(":
                depth += 1
                out.append(" ")
            elif ch == ")":
                depth = max(0, depth - 1)
                out.append(" ")
            else:
                out.append(ch if depth == 0 else " ")
        return "".join(out).rstrip()


# ===========================================================================
# Hàm tiện ích cấp module
# ===========================================================================

_default_guardrails: SQLGuardrails | None = None


def _get_default() -> SQLGuardrails:
    global _default_guardrails
    if _default_guardrails is None:
        _default_guardrails = SQLGuardrails()
    return _default_guardrails


def validate_sql(sql: str) -> ValidationResult:
    """Kiểm duyệt SQL với cấu hình mặc định."""
    return _get_default().validate_sql(sql)


def sanitize_sql(sql: str) -> str:
    """Làm sạch SQL với cấu hình mặc định."""
    return _get_default().sanitize_sql(sql)


def format_sql(sql: str) -> str:
    """Format SQL cho dễ đọc (dùng để hiển thị, không dùng để thực thi)."""
    return sqlparse.format(sql, reindent=True, keyword_case="upper").strip()
