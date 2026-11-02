"""OpenTelemetry traces: one trace per case run with a span per agent step, model call and MCP tool call.

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set. The standard OTEL_* variables configure everything else, so any OTLP
backend works: Jaeger locally, Langfuse (EU cloud), Azure Monitor, Grafana. The MCP SDK propagates the trace context
to the core-banking server, so tool calls show up inside the agent's trace.
"""

import os
from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig
from opentelemetry import trace
from opentelemetry.propagate import extract, inject

tracer = trace.get_tracer("clearline")

# Message content in spans is opt-in (OTel GenAI convention); the text is already PII-redacted, but traces may leave the EU.
CAPTURE_CONTENT = os.getenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "").lower() == "true"


def setup() -> None:
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider()  # service name from OTEL_SERVICE_NAME
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


def carrier(span: trace.Span) -> dict[str, str]:
    """W3C traceparent for a span, as plain strings: safe to pass through LangGraph config and checkpoints."""
    out: dict[str, str] = {}
    inject(out, context=trace.set_span_in_context(span))
    return out


def node(fn: Callable[[Any], dict]):  # inferred return type keeps the `config` name LangGraph matches on
    """Run a graph node in a span under the case's root span (a W3C carrier under `trace` in the run config)."""
    def wrapper(state: Any, config: RunnableConfig) -> dict:
        parent = extract((config.get("configurable") or {}).get("trace") or {})
        with tracer.start_as_current_span(fn.__name__, context=parent):
            return fn(state)
    return wrapper
