"""
OpenTelemetry support for FastAPI, exporting traces to Langfuse.

Requires opentelemetry-instrumentation-fastapi and related packages.
Enable by setting LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY (optional: LANGFUSE_HOST).
"""

from __future__ import annotations

import base64
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def _configure_langfuse_otlp() -> bool:
    """If Langfuse keys are set, configure env for OTLP export to Langfuse. Returns True if set."""
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not pk or not sk:
        return False
    host = os.getenv("LANGFUSE_BASE_URL")
    endpoint = f"{host}/api/public/otel"
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth}"
    return True


def instrument_fastapi(app: FastAPI) -> bool:
    """
    Instrument a FastAPI app with OpenTelemetry and export traces to Langfuse.

    Enable by setting LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in the environment.

    Returns:
        True if instrumentation was applied, False if Langfuse not configured or packages missing.
    """
    if not _configure_langfuse_otlp():
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # pyright: ignore[reportMissingImports]
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import (  # pyright: ignore[reportMissingImports]
            FastAPIInstrumentor,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False

    service_name = os.getenv("OTEL_SERVICE_NAME", "file-server")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/health",
    )
    print("OTEL: Exporting traces to Langfuse.", file=sys.stderr)
    return True
