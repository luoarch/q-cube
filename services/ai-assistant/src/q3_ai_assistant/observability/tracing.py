"""Tracing helpers for council operations.

Uses OpenTelemetry SDK for distributed tracing. Falls back to structured
logging when no OTLP exporter endpoint is configured.

Environment variables:
  OTEL_EXPORTER_OTLP_ENDPOINT — e.g. http://localhost:4317 (enables OTLP export)
  OTEL_SERVICE_NAME — defaults to "q3-ai-assistant"
  Q3_OTEL_CONSOLE_EXPORT — set to "1" to also print spans to console (dev)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)

# Module-level tracer — initialized once via setup_tracing()
_tracer: trace.Tracer | None = None


def setup_tracing() -> None:
    """Initialize the OTel TracerProvider with configured exporters.

    Call once at application startup (from main.py).
    """
    global _tracer

    service_name = os.getenv("OTEL_SERVICE_NAME", "q3-ai-assistant")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    # OTLP gRPC exporter (production)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("otel_otlp_exporter endpoint=%s", otlp_endpoint)
        except Exception:
            logger.warning("otel_otlp_exporter_failed endpoint=%s", otlp_endpoint, exc_info=True)

    # Console exporter (dev)
    if os.getenv("Q3_OTEL_CONSOLE_EXPORT") == "1":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("q3-ai-assistant")


def get_tracer() -> trace.Tracer:
    """Get the module tracer, initializing if needed."""
    global _tracer
    if _tracer is None:
        setup_tracing()
    assert _tracer is not None
    return _tracer


# ---------------------------------------------------------------------------
# Lightweight Span dataclass — kept for backward compatibility with tests
# ---------------------------------------------------------------------------

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
    """Context manager that tracks a span via OTel and returns a lightweight Span.

    Creates a real OTel span for distributed tracing, and also yields a
    local Span dataclass for direct access to duration/attributes.
    """
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

    tracer = get_tracer()
    with tracer.start_as_current_span(
        name,
        attributes={k: v for k, v in attributes.items() if isinstance(v, (str, int, float, bool))},
    ) as otel_span:
        try:
            yield span
        except Exception as exc:
            span.status = "error"
            otel_span.set_status(StatusCode.ERROR, str(exc))
            otel_span.record_exception(exc)
            raise
        finally:
            span.end_time_ms = time.monotonic() * 1000
            otel_span.set_attribute("duration_ms", span.duration_ms)
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
