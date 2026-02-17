from typing import Any

from langchain.tools import ToolRuntime, tool

from autobots_devtools_shared_lib.common.utils.context_utils import (
    clear_context,
    get_context,
    resolve_context_key,
    set_context,
    update_context,
)
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent


@tool
def get_context_tool(runtime: ToolRuntime[None, Dynagent]) -> dict[str, Any]:
    """Return the current session context as a JSON-serializable dict.

    The context is loaded from the configured ContextStore backend using the
    context_key found in the agent state. If no context exists yet, an empty
    dict is returned.
    """
    context_key = resolve_context_key(runtime.state)
    return get_context(context_key)


@tool
def set_context_tool(runtime: ToolRuntime[None, Dynagent], data: dict[str, Any]) -> str:
    """Replace the current session context with the provided data."""
    context_key = resolve_context_key(runtime.state)
    return set_context(context_key, data)


@tool
def update_context_tool(
    runtime: ToolRuntime[None, Dynagent], patch: dict[str, Any]
) -> dict[str, Any]:
    """Apply a partial update to the session context and return the new context."""
    context_key = resolve_context_key(runtime.state)
    return update_context(context_key, patch)


@tool
def clear_context_tool(runtime: ToolRuntime[None, Dynagent]) -> str:
    """Clear any stored context for the current session."""
    context_key = resolve_context_key(runtime.state)
    return clear_context(context_key)
