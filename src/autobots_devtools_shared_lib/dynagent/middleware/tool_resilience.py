# ABOUTME: Middleware that converts tool exceptions into error ToolMessages.
# ABOUTME: Keeps the deep-agent run alive so the model can adjust inputs and retry.

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage

from autobots_devtools_shared_lib.common.observability import get_logger

logger = get_logger(__name__)

_MAX_ERROR_CHARS = 500


def _error_tool_message(request: ToolCallRequest, exc: Exception) -> ToolMessage:
    tool_name = request.tool_call.get("name", "unknown")
    summary = f"{type(exc).__name__}: {exc}"[:_MAX_ERROR_CHARS]
    logger.warning(f"Tool '{tool_name}' raised; returning error ToolMessage: {summary}")
    return ToolMessage(
        content=(
            f"Tool '{tool_name}' failed: {summary}. Adjust the inputs or take a different approach."
        ),
        tool_call_id=request.tool_call.get("id", ""),
        name=tool_name,
        status="error",
    )


class ToolResilienceMiddleware(AgentMiddleware):
    """Convert tool exceptions to error ToolMessages instead of aborting the run."""

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        try:
            return handler(request)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return _error_tool_message(request, exc)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        try:
            return await handler(request)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return _error_tool_message(request, exc)
