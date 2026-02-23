"""
OpenTelemetry trace propagation helpers for HTTP client calls.

Provides W3C traceparent header injection and session linking for fileserver HTTP calls.
Reuses Langfuse configuration (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST).
"""

from __future__ import annotations

import base64
import os
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

# Global state for lazy initialization
_tracer_provider_initialized = False
_otel_available = False


def _ensure_tracer_provider() -> bool:
    """
    Ensure OTEL tracer provider is initialized with Langfuse export.

    Lazy initialization pattern - only creates provider on first use.
    Reuses existing provider if already configured (e.g., in fileserver).
    Returns False if OTEL unavailable or Langfuse not configured.

    Returns:
        True if provider is available, False otherwise (never raises)
    """
    global _tracer_provider_initialized, _otel_available

    # Fast path: already tried initialization
    if _tracer_provider_initialized:
        return _otel_available

    _tracer_provider_initialized = True

    try:
        # Check if OTEL packages available
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,  # pyright: ignore[reportMissingImports]
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        print(
            "OTEL: Packages not available, trace propagation disabled.",
            file=sys.stderr,
        )
        _otel_available = False
        return False

    # Check Langfuse configuration
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not pk or not sk:
        print(
            "OTEL: Langfuse keys not configured, trace propagation disabled.",
            file=sys.stderr,
        )
        _otel_available = False
        return False

    # Check if provider already exists (e.g., fileserver already instrumented)
    provider = trace.get_tracer_provider()
    if type(provider).__name__ != "ProxyTracerProvider":
        print(
            "OTEL: Existing tracer provider detected, reusing for trace propagation.",
            file=sys.stderr,
        )
        _otel_available = True
        return True

    try:
        # Configure OTLP endpoint (same pattern as otel_fastapi.py)
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        endpoint = f"{host}/api/public/otel"
        auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth}"

        # Create TracerProvider with service name
        service_name = os.getenv("OTEL_SERVICE_NAME", "dynagent-client")
        resource = Resource.create({"service.name": service_name})
        new_provider = TracerProvider(resource=resource)

        # Add OTLP exporter with batch processing
        exporter = OTLPSpanExporter()
        new_provider.add_span_processor(BatchSpanProcessor(exporter))

        # Set as global provider
        trace.set_tracer_provider(new_provider)

        print(
            f"OTEL: Initialized trace propagation for {service_name} -> {endpoint}",
            file=sys.stderr,
        )
        _otel_available = True

    except Exception as e:
        print(
            f"OTEL: Failed to initialize tracer provider: {e}",
            file=sys.stderr,
        )
        _otel_available = False
    else:
        return True
    return False


@contextmanager
def traced_http_call(
    operation: str,
    session_id: str | None = None,
    user_id: str | None = None,
) -> Generator[dict[str, str], None, None]:
    """
    Context manager that creates an OTEL client span and injects W3C traceparent header.

    Links HTTP calls to Langfuse sessions via langfuse.session.id attribute.
    Gracefully degrades to empty headers if OTEL unavailable.

    Args:
        operation: Operation name (e.g., "writeFile", "readFile")
        session_id: Optional session ID to link trace to Langfuse session
        user_id: Optional user ID for trace metadata

    Yields:
        Dict of HTTP headers to include in request (empty if OTEL unavailable)

    Example:
        >>> with traced_http_call("writeFile", session_id="abc123") as headers:
        ...     response = httpx.post(url, json=payload, headers=headers)
    """
    # Fast path: OTEL not available
    if not _ensure_tracer_provider():
        yield {}
        return

    try:
        from opentelemetry import trace
        from opentelemetry.trace import SpanKind
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    except ImportError:
        yield {}
        return

    try:
        # Get tracer and create CLIENT span
        tracer = trace.get_tracer(__name__)
        headers: dict[str, str] = {}

        with tracer.start_as_current_span(
            f"http.client.{operation}",
            kind=SpanKind.CLIENT,
        ) as span:
            # Set span attributes for Langfuse session linking
            if session_id is not None:
                span.set_attribute("langfuse.session.id", str(session_id))
            if user_id is not None:
                span.set_attribute("langfuse.user.id", str(user_id))
            span.set_attribute("http.operation", operation)

            # Inject W3C traceparent header
            TraceContextTextMapPropagator().inject(headers)

            yield headers

    except Exception as e:
        print(
            f"OTEL: Failed to create trace for {operation}: {e}",
            file=sys.stderr,
        )
        yield {}
