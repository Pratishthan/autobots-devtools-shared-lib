import logging
import os
import sys
from contextvars import ContextVar

LogLevelLike = int | str

_logging_configured: bool = False


class ConversationFilter(logging.Filter):
    """
    Inject a conversation/thread identifier into every log record.

    This enables log format strings to include `%(conversation_id)s`
    for tracing multi-message conversations across threads/tasks.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        record.conversation_id = _conversation_id_var.get()
        return True


# Thread-safe context for the current conversation/thread id.
_conversation_id_var: ContextVar[str] = ContextVar(
    "conversation_id", default="default-conversation-id"
)


def set_conversation_id(thread_id: str) -> None:
    """
    Set the conversation/thread identifier for the current context.

    Args:
        thread_id: Identifier for the current conversation/thread.
    """
    _conversation_id_var.set(thread_id)


def _parse_log_level(level: LogLevelLike | None) -> int:
    """
    Normalize various level representations into a standard logging level.
    """
    if level is None:
        return logging.INFO

    if isinstance(level, int):
        # Clamp to logging's supported range, but don't be too strict.
        return max(0, min(50, level))

    value = str(level).strip()
    if not value:
        return logging.INFO

    # Numeric string (e.g. "10", "20")
    if value.isdigit():
        return _parse_log_level(int(value))

    # Named level (DEBUG, INFO, etc.)
    value = value.upper()
    numeric = getattr(logging, value, None)
    if isinstance(numeric, int):
        return numeric

    # Fallback
    return logging.INFO


def setup_logging(
    level: LogLevelLike | None = None,
    fmt: str | None = None,
    force: bool = False,
) -> None:
    """
    Initialize process-wide logging configuration.

    This is safe to call multiple times; configuration will only be applied once
    unless `force=True` is passed.

    Precedence for the log level:
        1. `level` argument (if provided)
        2. `LOG_LEVEL` environment variable
        3. Default: logging.INFO

    Args:
        level: Explicit log level (int or name like "DEBUG").
        fmt: Log format string. If omitted, a default including conversation_id is used.
        force: If True, reconfigure logging even if it was already configured.
    """
    global _logging_configured

    if _logging_configured and not force:
        return

    # Determine effective level
    env_level = os.getenv("LOG_LEVEL")
    effective_level = _parse_log_level(level if level is not None else env_level)

    # Default format includes conversation/thread context
    log_format = fmt or (
        "%(asctime)s - %(name)s - [%(conversation_id)s] - %(levelname)s - %(message)s"
    )

    root_logger = logging.getLogger()

    if force or not _logging_configured:
        # Clear existing handlers to avoid duplicate logs
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    root_logger.setLevel(effective_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(effective_level)
    handler.setFormatter(logging.Formatter(log_format))
    handler.addFilter(ConversationFilter())

    root_logger.addHandler(handler)

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger, ensuring logging is initialized first.
    """
    if not _logging_configured:
        setup_logging()
    return logging.getLogger(name)


def get_agent_logger(name: str) -> logging.Logger:
    """
    Semantic alias for agent-related loggers.

    Equivalent to `get_logger(name)`, but keeps call sites self-documenting.
    """
    return get_logger(name)


def set_log_level(level: LogLevelLike) -> None:
    """
    Dynamically adjust the root logger's level at runtime.

    Args:
        level: New log level as int or string.
    """
    numeric_level = _parse_log_level(level)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    for handler in root_logger.handlers:
        handler.setLevel(numeric_level)
