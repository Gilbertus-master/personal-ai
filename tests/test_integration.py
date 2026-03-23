"""
Integration tests for Gilbertus Albans.
Tests that require running services (Postgres, Qdrant) are marked with pytest.mark.
Run with: .venv/bin/python -m pytest tests/test_integration.py -v
"""
import os
import pytest
from unittest.mock import patch

# ── DB integration tests (require Postgres) ──

@pytest.fixture
def pg_connection():
    """Get a real Postgres connection. Skip if not available."""
    try:
        from app.db.postgres import get_pg_connection
        conn = get_pg_connection()
        yield conn
        conn.close()
    except Exception:
        pytest.skip("Postgres not available")


def test_pg_connection(pg_connection):
    with pg_connection.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1


def test_pg_tables_exist(pg_connection):
    with pg_connection.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
        )
        tables = [row[0] for row in cur.fetchall()]

    required = ["sources", "documents", "chunks", "entities", "events", "summaries"]
    for table in required:
        assert table in tables, f"Missing table: {table}"


def test_pg_data_exists(pg_connection):
    with pg_connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents")
        doc_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM chunks")
        chunk_count = cur.fetchone()[0]

    assert doc_count > 0, "No documents in database"
    assert chunk_count > 0, "No chunks in database"


def test_pg_source_types(pg_connection):
    with pg_connection.cursor() as cur:
        cur.execute("SELECT DISTINCT source_type FROM sources ORDER BY source_type")
        types = [row[0] for row in cur.fetchall()]

    assert len(types) > 0, "No source types"
    # At least some of these should exist
    expected_any = {"whatsapp", "chatgpt", "email", "document", "teams", "spreadsheet"}
    assert len(set(types) & expected_any) > 0, f"No expected source types found in {types}"


# ── Ingestion DB function tests ──

def test_document_exists_by_raw_path():
    from app.ingestion.common.db import document_exists_by_raw_path
    # Non-existent path — uses its own connection
    assert document_exists_by_raw_path("__nonexistent_test_path__") is False


# ── Query interpreter tests (require Anthropic API) ──

def test_query_interpreter_fallback():
    """Test that interpreter returns fallback when API is unavailable."""
    from app.retrieval.query_interpreter import build_fallback_interpretation
    result = build_fallback_interpretation(
        query="co mówiłem o tradingu?",
        source_types=None,
        source_names=None,
        date_from=None,
        date_to=None,
    )
    assert result.normalized_query == "co mówiłem o tradingu?"
    assert result.question_type == "retrieval"


# ── Postprocessing tests ──

def test_cleanup_matches_dedup():
    from app.retrieval.postprocess import cleanup_matches
    matches = [
        {"document_id": 1, "text": "Hello world " * 30, "score": 0.9, "source_type": "test"},
        {"document_id": 1, "text": "Hello world " * 30, "score": 0.85, "source_type": "test"},
        {"document_id": 2, "text": "Different text " * 30, "score": 0.8, "source_type": "test"},
    ]
    cleaned, stats = cleanup_matches(matches, normalized_query="test", top_k=10)
    # Should dedup the duplicate
    assert len(cleaned) <= len(matches)
    assert stats["dedup_filtered_out"] >= 1


def test_cleanup_matches_empty():
    from app.retrieval.postprocess import cleanup_matches
    cleaned, stats = cleanup_matches([], normalized_query="test", top_k=10)
    assert cleaned == []
    assert stats["input_count"] == 0


# ── Redaction tests ──

def test_redact_matches_password():
    from app.retrieval.redaction import redact_matches
    matches = [
        {"text": "My password is secret123", "score": 0.9},
    ]
    redacted, count = redact_matches(matches)
    assert "REDACTED" in redacted[0]["text"].upper()
    assert count > 0


def test_redact_matches_clean():
    from app.retrieval.redaction import redact_matches
    matches = [
        {"text": "This is a normal message about work.", "score": 0.9},
    ]
    redacted, count = redact_matches(matches)
    assert redacted[0]["text"] == "This is a normal message about work."
    assert count == 0


# ── Timeline tests ──

def test_timeline_build_query():
    from app.retrieval.timeline import build_query
    sql, params = build_query(event_type="decision", date_from="2026-01-01", date_to=None, limit=10)
    assert "e.event_type = %s" in sql
    assert params[0] == "decision"
    assert params[-1] == 10


def test_timeline_query_no_filters():
    from app.retrieval.timeline import build_query
    sql, params = build_query(event_type=None, date_from=None, date_to=None, limit=5)
    assert "WHERE" not in sql
    assert params == [5]


# ── Summary module tests ──

def test_summary_fetch_chunks(pg_connection):
    from app.retrieval.summaries import fetch_chunks_for_period
    chunks = fetch_chunks_for_period("2026-03-01", "2026-03-31", area="general", limit=5)
    # Should return some chunks (we have data in this period)
    assert isinstance(chunks, list)


def test_summary_get_empty():
    from app.retrieval.summaries import get_summaries
    results = get_summaries(summary_type="daily", area="general", limit=5)
    assert isinstance(results, list)


# ── API schema tests ──

def test_ask_request_validation():
    from app.api.schemas import AskRequest
    req = AskRequest(query="test query")
    assert req.top_k == 8
    assert req.debug is False


def test_ask_request_empty_query():
    from app.api.schemas import AskRequest
    with pytest.raises(Exception):
        AskRequest(query="")


# ── Qdrant search tests (require Qdrant with data) ──

@pytest.fixture
def qdrant_ready():
    """Check if Qdrant has data. Skip if empty."""
    try:
        import requests
        resp = requests.get("http://127.0.0.1:6333/collections/gilbertus_chunks", timeout=5)
        data = resp.json()
        points = data.get("result", {}).get("points_count", 0)
        if points < 100:
            pytest.skip(f"Qdrant has only {points} points, need at least 100")
    except Exception:
        pytest.skip("Qdrant not available")


def test_search_chunks_basic(qdrant_ready):
    from app.retrieval.retriever import search_chunks
    results = search_chunks(query="trading energia", top_k=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "text" in results[0]
    assert "score" in results[0]


def test_search_chunks_with_source_filter(qdrant_ready):
    from app.retrieval.retriever import search_chunks
    results = search_chunks(
        query="email test",
        top_k=3,
        source_types=["email"],
    )
    assert isinstance(results, list)
    for r in results:
        assert r.get("source_type") == "email"
