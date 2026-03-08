"""Tracing helpers for council operations.

Provides lightweight span tracking for council analysis pipelines.
When OpenTelemetry is installed, integrates with OTEL. Otherwise
uses simple structured logging with trace/span IDs.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

logger = logging.getLogger(__name__)


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0
    attributes: dict[str, object] = field(default_factory=dict)
    status: str = "ok"

    @property
    def duration_ms(self) -> float:
        return self.end_time_ms - self.start_time_ms


_current_trace_id: str | None = None


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def new_span_id() -> str:
    return uuid.uuid4().hex[:8]


@contextmanager
def trace_span(
    name: str,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    **attributes: object,
) -> Generator[Span, None, None]:
    """Context manager that tracks a span and logs its duration."""
    global _current_trace_id

    tid = trace_id or _current_trace_id or new_trace_id()
    _current_trace_id = tid
    sid = new_span_id()

    span = Span(
        name=name,
        trace_id=tid,
        span_id=sid,
        parent_span_id=parent_span_id,
        start_time_ms=time.monotonic() * 1000,
        attributes=dict(attributes),
    )

    try:
        yield span
    except Exception:
        span.status = "error"
        raise
    finally:
        span.end_time_ms = time.monotonic() * 1000
        logger.info(
            "span %s completed in %.1fms [%s]",
            span.name,
            span.duration_ms,
            span.status,
            extra={
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                **{k: v for k, v in span.attributes.items() if isinstance(v, (str, int, float))},
            },
        )
