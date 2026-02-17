"""Unit tests for OTEL request/response capture utilities."""

import json
from unittest.mock import MagicMock

import pytest

from autobots_devtools_shared_lib.common.observability.otel_fastapi import (
    OtelCaptureConfig,
    _capture_error_details,
    _truncate_body,
)


class TestOtelCaptureConfig:
    """Tests for OtelCaptureConfig class."""

    def test_default_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default configuration values."""
        # Clear any existing env vars
        monkeypatch.delenv("OTEL_CAPTURE_ENABLED", raising=False)
        monkeypatch.delenv("OTEL_CAPTURE_MAX_BODY_SIZE_KB", raising=False)
        monkeypatch.delenv("OTEL_CAPTURE_EXCLUDE_PATHS", raising=False)

        config = OtelCaptureConfig()
        assert config.enabled is True
        assert config.max_body_size_kb == 10
        assert config.excluded_paths == ["/health", "/docs", "/redoc"]

    def test_enabled_true_variants(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test various ways to enable capture."""
        for value in ["true", "TRUE", "True", "1", "yes", "YES"]:
            monkeypatch.setenv("OTEL_CAPTURE_ENABLED", value)
            config = OtelCaptureConfig()
            assert config.enabled is True, f"Failed for value: {value}"

    def test_enabled_false_variants(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test various ways to disable capture."""
        for value in ["false", "FALSE", "0", "no", "NO", "other"]:
            monkeypatch.setenv("OTEL_CAPTURE_ENABLED", value)
            config = OtelCaptureConfig()
            assert config.enabled is False, f"Failed for value: {value}"

    def test_custom_max_body_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom max body size."""
        monkeypatch.setenv("OTEL_CAPTURE_MAX_BODY_SIZE_KB", "50")
        config = OtelCaptureConfig()
        assert config.max_body_size_kb == 50

    def test_custom_excluded_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom excluded paths."""
        monkeypatch.setenv("OTEL_CAPTURE_EXCLUDE_PATHS", "/api/v1,/metrics,/status")
        config = OtelCaptureConfig()
        assert config.excluded_paths == ["/api/v1", "/metrics", "/status"]

    def test_excluded_paths_with_spaces(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test excluded paths with leading/trailing spaces."""
        monkeypatch.setenv("OTEL_CAPTURE_EXCLUDE_PATHS", " /api/v1 , /metrics , /status ")
        config = OtelCaptureConfig()
        assert config.excluded_paths == ["/api/v1", "/metrics", "/status"]


class TestTruncateBody:
    """Tests for _truncate_body function."""

    def test_small_body_utf8(self) -> None:
        """Test small body that doesn't need truncation."""
        body = b"Hello, World!"
        result = _truncate_body(body, max_size_kb=10)

        assert result["content"] == "Hello, World!"
        assert result["size_bytes"] == 13
        assert result["truncated"] is False
        assert result["encoding"] == "utf-8"

    def test_large_body_truncation(self) -> None:
        """Test body that exceeds max size gets truncated."""
        # Create 15KB body
        body = b"x" * (15 * 1024)
        result = _truncate_body(body, max_size_kb=10)

        # Should be truncated to 10KB
        max_bytes = 10 * 1024
        assert len(result["content"]) > max_bytes  # Includes truncation message
        assert result["size_bytes"] == 15 * 1024
        assert result["truncated"] is True
        assert result["encoding"] == "utf-8"
        assert "[... truncated" in result["content"]
        assert "5120 bytes ...]" in result["content"]  # 15KB - 10KB = 5KB = 5120 bytes

    def test_exact_size_no_truncation(self) -> None:
        """Test body exactly at max size is not truncated."""
        body = b"x" * (10 * 1024)
        result = _truncate_body(body, max_size_kb=10)

        assert result["truncated"] is False
        assert result["size_bytes"] == 10 * 1024

    def test_binary_body_base64_encoding(self) -> None:
        """Test binary body gets base64 encoded."""
        # Create binary data that can't be decoded as UTF-8
        body = bytes([0xFF, 0xFE, 0xFD, 0xFC, 0x00, 0x01, 0x02])
        result = _truncate_body(body, max_size_kb=10)

        assert result["encoding"] == "base64"
        assert result["truncated"] is False
        # Verify it's valid base64
        import base64

        decoded = base64.b64decode(result["content"])
        assert decoded == body

    def test_binary_body_truncation(self) -> None:
        """Test large binary body gets truncated and base64 encoded."""
        # Create 15KB of binary data
        body = bytes([i % 256 for i in range(15 * 1024)])
        result = _truncate_body(body, max_size_kb=10)

        assert result["encoding"] == "base64"
        assert result["truncated"] is True
        assert result["size_bytes"] == 15 * 1024
        assert "[... truncated" in result["content"]

    def test_empty_body(self) -> None:
        """Test empty body."""
        body = b""
        result = _truncate_body(body, max_size_kb=10)

        assert result["content"] == ""
        assert result["size_bytes"] == 0
        assert result["truncated"] is False
        assert result["encoding"] == "utf-8"

    def test_json_body(self) -> None:
        """Test JSON body is handled correctly."""
        data = {"key": "value", "number": 42, "nested": {"foo": "bar"}}
        body = json.dumps(data).encode("utf-8")
        result = _truncate_body(body, max_size_kb=10)

        assert result["encoding"] == "utf-8"
        assert result["truncated"] is False
        # Verify we can parse it back
        parsed = json.loads(result["content"])
        assert parsed == data


class TestCaptureErrorDetails:
    """Tests for _capture_error_details function."""

    def test_json_error_with_detail(self) -> None:
        """Test JSON error response with 'detail' field."""
        span = MagicMock()
        error_body = json.dumps({"detail": "File not found"}).encode("utf-8")

        _capture_error_details(span, error_body)

        span.set_attribute.assert_called_once_with("http.response.error.detail", "File not found")

    def test_json_error_with_message(self) -> None:
        """Test JSON error response with 'message' field."""
        span = MagicMock()
        error_body = json.dumps({"message": "Invalid request"}).encode("utf-8")

        _capture_error_details(span, error_body)

        span.set_attribute.assert_called_once_with("http.response.error.message", "Invalid request")

    def test_json_error_detail_preferred_over_message(self) -> None:
        """Test that 'detail' is preferred when both fields exist."""
        span = MagicMock()
        error_body = json.dumps({"detail": "Primary error", "message": "Secondary"}).encode("utf-8")

        _capture_error_details(span, error_body)

        # Should use 'detail' not 'message'
        span.set_attribute.assert_called_once_with("http.response.error.detail", "Primary error")

    def test_plain_text_error(self) -> None:
        """Test plain text error response (non-JSON)."""
        span = MagicMock()
        error_body = b"Internal Server Error"

        _capture_error_details(span, error_body)

        span.set_attribute.assert_called_once_with(
            "http.response.error.raw", "Internal Server Error"
        )

    def test_binary_error_response(self) -> None:
        """Test binary error response."""
        span = MagicMock()
        error_body = bytes([0xFF, 0xFE, 0xFD] * 100)  # Binary data

        _capture_error_details(span, error_body)

        # Should fallback to raw capture with error replacement
        span.set_attribute.assert_called_once()
        call_args = span.set_attribute.call_args
        assert call_args[0][0] == "http.response.error.raw"
        assert len(call_args[0][1]) <= 200  # Should be truncated to 200 chars

    def test_invalid_json_error(self) -> None:
        """Test malformed JSON error response."""
        span = MagicMock()
        error_body = b'{"invalid": json}'

        _capture_error_details(span, error_body)

        span.set_attribute.assert_called_once_with("http.response.error.raw", '{"invalid": json}')

    def test_long_error_message_truncation(self) -> None:
        """Test that raw errors are truncated to 200 bytes."""
        span = MagicMock()
        error_body = b"x" * 500  # 500 bytes of error text

        _capture_error_details(span, error_body)

        call_args = span.set_attribute.call_args
        captured_error = call_args[0][1]
        assert len(captured_error) == 200  # Should be truncated
        assert captured_error == "x" * 200

    def test_complex_json_error(self) -> None:
        """Test complex JSON error with nested structure."""
        span = MagicMock()
        error_data = {
            "detail": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input",
                "fields": ["name", "email"],
            }
        }
        error_body = json.dumps(error_data).encode("utf-8")

        _capture_error_details(span, error_body)

        # Should convert dict to string
        span.set_attribute.assert_called_once()
        call_args = span.set_attribute.call_args
        assert call_args[0][0] == "http.response.error.detail"
        assert "VALIDATION_ERROR" in call_args[0][1]
