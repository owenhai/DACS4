"""Consolidated Week 2 tests for the Text‑to‑SQL pipeline.

This file combines the prompt‑building test, the SQL‑generation test and the
full‑pipeline integration test that hits the real Gemini API.

The integration test is **skipped** when the required environment variable
``GEMINI_API_KEY`` is not set – this allows the test suite to run locally without
network access.  When the key is present the test will send a single request to
the Gemini model and verify that a SQL statement is produced and that it can be
executed against the DuckDB analytics database.
"""

import os
import pytest
from pathlib import Path

from src.models.text_to_sql import TextToSQLPipeline, QueryResult
from src.models.prompt_templates import build_text_to_sql_prompt, SYSTEM_INSTRUCTION

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pipeline() -> TextToSQLPipeline:
    """Create a pipeline instance for the entire test module.

    The ``TextToSQLPipeline`` will lazily create a ``GeminiClient``; the client
    reads the ``GEMINI_API_KEY`` from the environment when it initialises.
    """
    return TextToSQLPipeline()

@pytest.fixture(scope="module")
def api_key_present() -> bool:
    """True when the user has supplied a Gemini API key.

    The integration test is guarded by this fixture so that CI runs can skip the
    network‑dependent part.
    """
    return bool(os.getenv("GEMINI_API_KEY"))

# ---------------------------------------------------------------------------
# Prompt‑building test
# ---------------------------------------------------------------------------

def test_prompt_contains_schema_and_question(pipeline: TextToSQLPipeline):
    """Ensure the prompt builder injects the schema and the user question.

    The function ``build_text_to_sql_prompt`` is a thin wrapper around the static
    ``SYSTEM_INSTRUCTION`` and the few‑shot examples.  We verify that the result
    contains three required parts:

    1. The system instruction.
    2. The formatted schema text (loaded by the pipeline on construction).
    3. The user question.
    """
    user_q = "Tổng số đơn hàng trong hệ thống là bao nhiêu?"
    prompt = build_text_to_sql_prompt(
        user_question=user_q,
        schema_text=pipeline.schema_text,
        num_examples=2,
    )
    assert SYSTEM_INSTRUCTION.strip() in prompt
    assert pipeline.schema_text.strip() in prompt
    assert user_q in prompt

# ---------------------------------------------------------------------------
# SQL‑generation test (does not require a live model)
# ---------------------------------------------------------------------------

def test_generate_sql_structure(pipeline: TextToSQLPipeline):
    """Check that the generated SQL looks like a SELECT statement.

    The pipeline internally calls ``GeminiClient``.  When the API key is missing
    the client raises an exception; we deliberately catch it and assert that the
    exception message mentions the missing key.  When the key is present we only
    assert that the SQL starts with ``SELECT`` – a full verification would need a
    running model which is out of scope for a unit test.
    """
    question = "Tổng doanh thu của toàn bộ hệ thống là bao nhiêu?"
    try:
        sql = pipeline._generate_sql(question)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        # Expected when the API key is absent or the model is unavailable.
        # Accept both missing‑key and model‑not‑found messages.
        assert "GEMINI_API_KEY" in str(exc) or "not found" in str(exc)
        pytest.skip("Gemini API key not configured or model unavailable – cannot generate SQL.")
    else:
        assert isinstance(sql, str)
        assert sql.strip().upper().startswith("SELECT"), "Generated SQL should be a SELECT"

# ---------------------------------------------------------------------------
# Full‑pipeline integration test (requires Gemini API key)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set – integration test requires real API access",
)
def test_full_pipeline_integration(pipeline: TextToSQLPipeline):
    """Run the pipeline end‑to‑end and verify a successful result.

    The test uses a simple count query that is guaranteed to be supported by the
    Olist star‑schema.  We assert that:

    1. ``result.success`` is ``True``.
    2. ``result.generated_sql`` is a non‑empty string.
    3. ``result.dataframe`` is a ``pandas.DataFrame`` with at least one row.
    """
    question = "Tổng số đơn hàng trong hệ thống là bao nhiêu?"
    result: QueryResult = pipeline.ask(question)
    # Basic sanity checks
    assert result.success, f"Pipeline reported failure: {result.error_message}"
    assert result.generated_sql, "No SQL was generated"
    assert result.dataframe is not None, "Dataframe is None"
    # The result of a COUNT query should be a single scalar column.
    assert len(result.dataframe) > 0, "Result dataframe is empty"
    assert result.dataframe.shape[1] == 1, "Expected a single column for COUNT"

# End of file

