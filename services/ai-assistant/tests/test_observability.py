"""Tests for observability module — logging and tracing."""

import json
import logging

from q3_ai_assistant.observability.logging import DevFormatter, StructuredFormatter
from q3_ai_assistant.observability.tracing import Span, new_span_id, new_trace_id, trace_span


class TestStructuredFormatter:
    def test_formats_as_json(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="hello %s", args=("world",), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert "timestamp" in parsed

    def test_includes_extra_fields(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        record.agent_id = "greenblatt"  # type: ignore[attr-defined]
        record.ticker = "WEGE3"  # type: ignore[attr-defined]
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["agent_id"] == "greenblatt"
        assert parsed["ticker"] == "WEGE3"

    def test_excludes_absent_extra_fields(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "agent_id" not in parsed
        assert "ticker" not in parsed


class TestDevFormatter:
    def test_formats_readable(self):
        formatter = DevFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="hello", args=(), exc_info=None,
        )
        output = formatter.format(record)
        assert "INFO" in output
        assert "hello" in output
        assert "[test]" in output


class TestTraceIds:
    def test_trace_id_length(self):
        tid = new_trace_id()
        assert len(tid) == 16

    def test_span_id_length(self):
        sid = new_span_id()
        assert len(sid) == 8

    def test_unique(self):
        ids = {new_trace_id() for _ in range(100)}
        assert len(ids) == 100


class TestSpan:
    def test_duration_calculation(self):
        span = Span(name="test", trace_id="abc", span_id="123",
                     start_time_ms=1000.0, end_time_ms=1500.0)
        assert span.duration_ms == 500.0

    def test_default_status(self):
        span = Span(name="test", trace_id="abc", span_id="123")
        assert span.status == "ok"


class TestTraceSpan:
    def test_context_manager_returns_span(self):
        with trace_span("test_op") as span:
            assert span.name == "test_op"
            assert span.trace_id
            assert span.span_id

    def test_records_duration(self):
        with trace_span("test_op") as span:
            pass
        assert span.duration_ms >= 0

    def test_error_sets_status(self):
        try:
            with trace_span("fail_op") as span:
                raise ValueError("boom")
        except ValueError:
            pass
        assert span.status == "error"

    def test_attributes_passed_through(self):
        with trace_span("op", ticker="WEGE3", mode="roundtable") as span:
            pass
        assert span.attributes["ticker"] == "WEGE3"
        assert span.attributes["mode"] == "roundtable"

    def test_custom_trace_id(self):
        with trace_span("op", trace_id="custom123") as span:
            pass
        assert span.trace_id == "custom123"
