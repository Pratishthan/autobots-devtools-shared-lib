# ABOUTME: Langfuse tracing integration for bro-chat.
# ABOUTME: Sets up LLM observability using Langfuse's decorator-based API.

from typing import Any

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)

_langfuse_client: Langfuse | None = None


def init_tracing() -> bool:
    """
    Initialize Langfuse tracing.

    Reads configuration from environment via get_dynagent_settings().

    Returns:
        True if tracing was initialized successfully, False otherwise.
    """
    global _langfuse_client

    from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
        get_dynagent_settings,
    )

    settings = get_dynagent_settings()

    if not settings.is_langfuse_configured():
        logger.info("Langfuse not configured, tracing disabled")
        return False

    try:
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse tracing: {e}")
        return False

    else:
        logger.info("Langfuse tracing initialized successfully")
        return True


def get_langfuse_handler() -> CallbackHandler | None:
    """
    Get the Langfuse handler for use with LangChain/LangGraph.

    Returns:
        The Langfuse CallbackHandler if configured, None otherwise.
    """
    if _langfuse_client is None:
        return None

    from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
        get_dynagent_settings,
    )

    settings = get_dynagent_settings()
    return CallbackHandler(public_key=settings.langfuse_public_key)


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
