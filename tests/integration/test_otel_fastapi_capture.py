"""Integration tests for OTEL FastAPI ASGI middleware capture."""

import json
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from starlette.testclient import TestClient

from autobots_devtools_shared_lib.common.observability.otel_fastapi import (
    OtelCaptureConfig,
    _build_otel_capture_app,
)


class MockSpan:
    """Mock OpenTelemetry Span for testing."""

    def __init__(self, *, recording: bool = True) -> None:
        self.attributes: dict[str, Any] = {}
        self._recording = recording

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def is_recording(self) -> bool:
        return self._recording


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app with various endpoints."""
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.post("/echo")
    async def echo(data: dict[str, Any]) -> dict[str, Any]:
        return data

    @app.post("/large")
    async def large_response() -> dict[str, str]:
        return {"data": "x" * (15 * 1024)}

    @app.get("/error")
    async def error() -> None:
        raise HTTPException(status_code=404, detail="Resource not found")

    @app.get("/server_error")
    async def server_error() -> None:
        raise HTTPException(status_code=500, detail="Internal server error")

    return app


class TestMiddlewareCapture:
    """Integration tests for the ASGI capture middleware."""

    def test_captures_input_output_for_post(
        self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that POST request/response are captured as input.value/output.value."""
        monkeypatch.setenv("OTEL_CAPTURE_ENABLED", "true")
        monkeypatch.setenv("OTEL_CAPTURE_MAX_BODY_SIZE_KB", "10")
        config = OtelCaptureConfig()
        span = MockSpan()

        with patch("opentelemetry.trace.get_current_span", return_value=span):
            asgi_app = test_app.build_middleware_stack()
            wrapped = _build_otel_capture_app(asgi_app, config)
            client = TestClient(wrapped)
            response = client.post("/echo", json={"message": "Hello, World!"})

        assert response.status_code == 200

        # Verify input.value was set
        assert "input.value" in span.attributes
        input_data = json.loads(span.attributes["input.value"])
        assert input_data["method"] == "POST"
        assert input_data["path"] == "/echo"
        assert "body" in input_data

        # Verify output.value was set
        assert "output.value" in span.attributes
        output_data = json.loads(span.attributes["output.value"])
        assert output_data["status"] == 200
        assert "body" in output_data

    def test_captures_get_request_excluded(
        self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that GET to excluded path skips capture."""
        monkeypatch.setenv("OTEL_CAPTURE_ENABLED", "true")
        config = OtelCaptureConfig()
        span = MockSpan()

        with patch("opentelemetry.trace.get_current_span", return_value=span):
            asgi_app = test_app.build_middleware_stack()
            wrapped = _build_otel_capture_app(asgi_app, config)
            client = TestClient(wrapped)
            response = client.get("/health")

        assert response.status_code == 200
        # /health is in default excluded_paths, so no attributes should be set
        assert "input.value" not in span.attributes

    def test_excluded_paths_skip_capture(
        self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that excluded paths don't capture data."""
        monkeypatch.setenv("OTEL_CAPTURE_ENABLED", "true")
        monkeypatch.setenv("OTEL_CAPTURE_EXCLUDE_PATHS", "/health,/docs")
        config = OtelCaptureConfig()
        span = MockSpan()

        with patch("opentelemetry.trace.get_current_span", return_value=span):
            asgi_app = test_app.build_middleware_stack()
            wrapped = _build_otel_capture_app(asgi_app, config)
            client = TestClient(wrapped)
            response = client.get("/health")

        assert response.status_code == 200
        assert "input.value" not in span.attributes
        assert "output.value" not in span.attributes

    def test_capture_disabled(self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that capture can be disabled."""
        monkeypatch.setenv("OTEL_CAPTURE_ENABLED", "false")
        config = OtelCaptureConfig()
        span = MockSpan()

        with patch("opentelemetry.trace.get_current_span", return_value=span):
            asgi_app = test_app.build_middleware_stack()
            wrapped = _build_otel_capture_app(asgi_app, config)
            client = TestClient(wrapped)
            response = client.post("/echo", json={"test": True})

        assert response.status_code == 200
        assert "input.value" not in span.attributes
        assert "output.value" not in span.attributes

    def test_error_response_capture(
        self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test capturing 404 error response with error detail in output."""
        monkeypatch.setenv("OTEL_CAPTURE_ENABLED", "true")
        config = OtelCaptureConfig()
        span = MockSpan()

        with patch("opentelemetry.trace.get_current_span", return_value=span):
            asgi_app = test_app.build_middleware_stack()
            wrapped = _build_otel_capture_app(asgi_app, config)
            client = TestClient(wrapped, raise_server_exceptions=False)
            response = client.get("/error")

        assert response.status_code == 404

        assert "output.value" in span.attributes
        output_data = json.loads(span.attributes["output.value"])
        assert output_data["status"] == 404
        assert output_data["error"] == "Resource not found"

    def test_500_error_capture(self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test capturing 500 error response."""
        monkeypatch.setenv("OTEL_CAPTURE_ENABLED", "true")
        config = OtelCaptureConfig()
        span = MockSpan()

        with patch("opentelemetry.trace.get_current_span", return_value=span):
            asgi_app = test_app.build_middleware_stack()
            wrapped = _build_otel_capture_app(asgi_app, config)
            client = TestClient(wrapped, raise_server_exceptions=False)
            response = client.get("/server_error")

        assert response.status_code == 500

        assert "output.value" in span.attributes
        output_data = json.loads(span.attributes["output.value"])
        assert output_data["status"] == 500
        assert output_data["error"] == "Internal server error"

    def test_large_response_truncation(
        self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that large responses get truncated in output.value."""
        monkeypatch.setenv("OTEL_CAPTURE_ENABLED", "true")
        monkeypatch.setenv("OTEL_CAPTURE_MAX_BODY_SIZE_KB", "10")
        config = OtelCaptureConfig()
        span = MockSpan()

        with patch("opentelemetry.trace.get_current_span", return_value=span):
            asgi_app = test_app.build_middleware_stack()
            wrapped = _build_otel_capture_app(asgi_app, config)
            client = TestClient(wrapped)
            response = client.post("/large")

        assert response.status_code == 200

        assert "output.value" in span.attributes
        output_data = json.loads(span.attributes["output.value"])
        assert output_data["status"] == 200
        assert output_data.get("truncated") is True
        assert output_data["body_size"] > 10 * 1024

    def test_span_not_recording_skips_attributes(
        self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that non-recording spans don't get attributes set."""
        monkeypatch.setenv("OTEL_CAPTURE_ENABLED", "true")
        config = OtelCaptureConfig()
        span = MockSpan(recording=False)

        with patch("opentelemetry.trace.get_current_span", return_value=span):
            asgi_app = test_app.build_middleware_stack()
            wrapped = _build_otel_capture_app(asgi_app, config)
            client = TestClient(wrapped)
            response = client.post("/echo", json={"test": True})

        assert response.status_code == 200
        assert len(span.attributes) == 0
