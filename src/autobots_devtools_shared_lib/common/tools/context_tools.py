from typing import Any

from langchain.tools import ToolRuntime, tool

from autobots_devtools_shared_lib.common.utils.context_utils import (
    clear_context,
    get_context,
    resolve_session_id,
    set_context,
    update_context,
)
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent


@tool
def get_context_tool(runtime: ToolRuntime[None, Dynagent]) -> dict[str, Any]:
    """Return the current session context as a JSON-serializable dict.

    The context is loaded from the configured ContextStore backend using the
    session_id found in the agent state. If no context exists yet, an empty
    dict is returned.
    """
    session_id = resolve_session_id(runtime.state)
    return get_context(session_id)


@tool
def set_context_tool(runtime: ToolRuntime[None, Dynagent], data: dict[str, Any]) -> str:
    """Replace the current session context with the provided data."""
    session_id = resolve_session_id(runtime.state)
    return set_context(session_id, data)


@tool
def update_context_tool(
    runtime: ToolRuntime[None, Dynagent], patch: dict[str, Any]
) -> dict[str, Any]:
    """Apply a partial update to the session context and return the new context."""
    session_id = resolve_session_id(runtime.state)
    return update_context(session_id, patch)


@tool
def clear_context_tool(runtime: ToolRuntime[None, Dynagent]) -> str:
    """Clear any stored context for the current session."""
    session_id = resolve_session_id(runtime.state)
    return clear_context(session_id)
