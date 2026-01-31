# ABOUTME: Langfuse tracing integration for bro-chat.
# ABOUTME: Sets up LLM observability using Langfuse's decorator-based API.

import logging
from typing import Any

from langfuse import Langfuse

from bro_chat.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_langfuse_client: Langfuse | None = None


def init_tracing(settings: Settings | None = None) -> bool:
    """
    Initialize Langfuse tracing.

    Args:
        settings: Optional settings instance. Uses get_settings() if not provided.

    Returns:
        True if tracing was initialized successfully, False otherwise.
    """
    global _langfuse_client

    if settings is None:
        settings = get_settings()

    if not settings.is_langfuse_configured():
        logger.info("Langfuse not configured, tracing disabled")
        return False

    try:
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

        logger.info("Langfuse tracing initialized successfully")
        return True

    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse tracing: {e}")
        return False


def get_langfuse_handler() -> Any:
    """
    Get the Langfuse handler for use with CrewAI.

    Note: CrewAI uses OpenTelemetry for tracing via traceloop-sdk.
    This function returns None as CrewAI handles its own instrumentation.

    Returns:
        None - CrewAI uses its own tracing integration.
    """
    return None


def get_langfuse_client() -> Langfuse | None:
    """
    Get the Langfuse client for direct API access.

    Returns:
        The Langfuse client if initialized, None otherwise.
    """
    return _langfuse_client


def create_trace(name: str, metadata: dict[str, Any] | None = None) -> Any:
    """
    Create a new Langfuse trace.

    Args:
        name: Name for the trace.
        metadata: Optional metadata to attach to the trace.

    Returns:
        The trace object if Langfuse is initialized, None otherwise.
    """
    if _langfuse_client is None:
        return None

    return _langfuse_client.trace(name=name, metadata=metadata or {})  # type: ignore[attr-defined]


def flush_tracing() -> None:
    """Flush any pending traces to Langfuse."""
    if _langfuse_client is not None:
        _langfuse_client.flush()
