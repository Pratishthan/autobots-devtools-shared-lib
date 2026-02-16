"""
OpenTelemetry support for FastAPI, exporting traces to Langfuse.

Requires opentelemetry-instrumentation-fastapi and related packages.
Enable by setting LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY (optional: LANGFUSE_HOST).
"""

from __future__ import annotations

import base64
import json
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI


class OtelCaptureConfig:
    """Configuration for OTEL request/response capture."""

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.enabled: bool = os.getenv("OTEL_CAPTURE_ENABLED", "true").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self.max_body_size_kb: int = int(os.getenv("OTEL_CAPTURE_MAX_BODY_SIZE_KB", "10"))
        self.excluded_paths: list[str] = [
            path.strip()
            for path in os.getenv("OTEL_CAPTURE_EXCLUDE_PATHS", "/health,/docs,/redoc").split(",")
        ]


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


def _truncate_body(body: bytes, max_size_kb: int) -> dict[str, Any]:
    """
    Truncate body if exceeds max_size_kb. Returns dict with content, size, truncated flag, encoding.

    Args:
        body: Raw body bytes
        max_size_kb: Maximum size in kilobytes

    Returns:
        Dict with keys: content (str), size_bytes (int), truncated (bool), encoding (str)
    """
    max_bytes = max_size_kb * 1024
    size_bytes = len(body)
    truncated = size_bytes > max_bytes

    # Truncate if needed
    captured_body = body[:max_bytes] if truncated else body

    # Try UTF-8 decode, fallback to base64
    try:
        content = captured_body.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = base64.b64encode(captured_body).decode("ascii")
        encoding = "base64"

    # Add truncation indicator
    if truncated:
        suffix = f"\n\n[... truncated {size_bytes - max_bytes} bytes ...]"
        content += suffix

    return {
        "content": content,
        "size_bytes": size_bytes,
        "truncated": truncated,
        "encoding": encoding,
    }


def _capture_error_details(span: Any, body: bytes) -> None:
    """
    Extract error message from response body for error responses.

    Args:
        span: OpenTelemetry span object
        body: Response body bytes
    """
    try:
        # Try parsing as JSON (FastAPI HTTPException format)
        body_str = body.decode("utf-8")
        error_data = json.loads(body_str)

        if "detail" in error_data:
            span.set_attribute("http.response.error.detail", str(error_data["detail"]))
        elif "message" in error_data:
            span.set_attribute("http.response.error.message", str(error_data["message"]))
    except (UnicodeDecodeError, json.JSONDecodeError):
        # Fallback: capture first 200 chars as raw error
        span.set_attribute("http.response.error.raw", body[:200].decode("utf-8", errors="replace"))


def _build_otel_capture_app(app: Any, config: OtelCaptureConfig) -> Any:
    """ASGI middleware that captures request/response bodies onto the current OTEL span.

    Uses ``input.value`` and ``output.value`` attribute names so Langfuse maps
    them directly to its Input/Output fields.

    Because this middleware wraps the OTEL-instrumented stack from the outside,
    span attributes must be set **inside** the ``send_wrapper`` (while the OTEL
    span is still active), not after ``await app(...)`` returns (by which point
    the OTEL middleware has already ended the span).
    """

    async def middleware(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or not config.enabled:
            await app(scope, receive, send)
            return

        # Check path exclusions
        path = scope.get("path", "/")
        if any(path.startswith(exc) for exc in config.excluded_paths):
            await app(scope, receive, send)
            return

        # --- Capture request body ---
        request_body_parts: list[bytes] = []

        async def receive_wrapper() -> dict[str, Any]:
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                if body:
                    request_body_parts.append(body)
            return message

        # --- Capture response status + body, set span attrs before final send ---
        response_status = 0
        response_body_parts: list[bytes] = []

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal response_status

            if message["type"] == "http.response.start":
                response_status = message.get("status", 0)
                await send(message)
                return

            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    response_body_parts.append(body)

                # On the final body chunk, set span attributes while span is
                # still active (OTEL middleware hasn't ended it yet).
                more_body = message.get("more_body", False)
                if not more_body:
                    _set_span_attributes(
                        scope,
                        path,
                        config,
                        request_body_parts,
                        response_status,
                        response_body_parts,
                    )

            await send(message)

        await app(scope, receive_wrapper, send_wrapper)

    return middleware


def _set_span_attributes(
    scope: dict[str, Any],
    path: str,
    config: OtelCaptureConfig,
    request_body_parts: list[bytes],
    response_status: int,
    response_body_parts: list[bytes],
) -> None:
    """Set ``input.value`` and ``output.value`` on the current OTEL span."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if not span or not span.is_recording():
            return

        # Build input dict (request metadata + body)
        input_data: dict[str, Any] = {
            "method": scope.get("method", ""),
            "path": path,
        }
        if request_body_parts:
            req_body = b"".join(request_body_parts)
            req_truncated = _truncate_body(req_body, config.max_body_size_kb)
            input_data["body"] = req_truncated["content"]
            input_data["body_size"] = req_truncated["size_bytes"]

        span.set_attribute("input.value", json.dumps(input_data))

        # Build output dict (status + body)
        output_data: dict[str, Any] = {"status": response_status}
        if response_body_parts:
            resp_body = b"".join(response_body_parts)
            resp_truncated = _truncate_body(resp_body, config.max_body_size_kb)
            output_data["body"] = resp_truncated["content"]
            output_data["body_size"] = resp_truncated["size_bytes"]
            if resp_truncated["truncated"]:
                output_data["truncated"] = True

            # Error details for 4xx/5xx
            if response_status >= 400:
                try:
                    err = json.loads(resp_body.decode("utf-8"))
                    if "detail" in err:
                        output_data["error"] = err["detail"]
                except Exception:  # noqa: S110
                    pass

        span.set_attribute("output.value", json.dumps(output_data))
    except Exception:  # noqa: S110
        pass  # Never break the request if tracing fails


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

    # Initialize config
    config = OtelCaptureConfig()

    service_name = os.getenv("OTEL_SERVICE_NAME", "file-server")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Build excluded URLs from config
    excluded_urls = ",".join(config.excluded_paths)

    # Standard OTEL instrumentation (gives us spans, timing, basic HTTP attrs)
    FastAPIInstrumentor.instrument_app(app, excluded_urls=excluded_urls)

    # Wrap with our ASGI middleware for input/output capture.
    # This MUST be applied AFTER FastAPIInstrumentor so it runs INSIDE the span.
    # Force-build the middleware stack first — Starlette builds it lazily on the
    # first request, so it would be None at this point.
    if app.middleware_stack is None:
        app.middleware_stack = app.build_middleware_stack()
    app.middleware_stack = _build_otel_capture_app(app.middleware_stack, config)

    print(
        f"OTEL: Exporting traces to Langfuse (capture_enabled={config.enabled}).", file=sys.stderr
    )
    print(
        "      Input/output data in Langfuse Input/Output fields (input.value / output.value)",
        file=sys.stderr,
    )
    return True
