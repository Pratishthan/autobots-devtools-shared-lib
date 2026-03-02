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


def make_context_tools(context_cls: type, state_cls: type = Dynagent) -> list[Any]:
    """Return context tools (get/set/update/clear) typed to the given context and state schemas.

    Args:
        context_cls: Pydantic-compatible model (e.g. MerContextData) whose fields and
                     Field(description=...) appear in the tool's JSON schema shown to the LLM.
        state_cls:   Agent state TypedDict used to type the injected runtime parameter.
                     Defaults to Dynagent. Invisible to the LLM.
    """

    def get_context_tool(runtime: ToolRuntime[None, Any]) -> dict[str, Any]:
        """Return the current session context as a JSON-serializable dict."""
        context_key = resolve_context_key(runtime.state)
        return get_context(context_key)

    get_context_tool.__annotations__["runtime"] = ToolRuntime[None, state_cls]

    def set_context_tool(runtime: ToolRuntime[None, Any], data: dict[str, Any]) -> str:
        """Replace the current session context with the provided data."""
        context_key = resolve_context_key(runtime.state)
        return set_context(context_key, dict(data))

    set_context_tool.__annotations__["runtime"] = ToolRuntime[None, state_cls]
    set_context_tool.__annotations__["data"] = context_cls

    def update_context_tool(
        runtime: ToolRuntime[None, Any], patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply a partial update to the session context and return the new context."""
        context_key = resolve_context_key(runtime.state)
        return update_context(context_key, dict(patch))

    update_context_tool.__annotations__["runtime"] = ToolRuntime[None, state_cls]
    update_context_tool.__annotations__["patch"] = context_cls

    def clear_context_tool(runtime: ToolRuntime[None, Any]) -> str:
        """Clear any stored context for the current session."""
        context_key = resolve_context_key(runtime.state)
        return clear_context(context_key)

    clear_context_tool.__annotations__["runtime"] = ToolRuntime[None, state_cls]

    return [
        tool(get_context_tool),
        tool(set_context_tool),
        tool(update_context_tool),
        tool(clear_context_tool),
    ]
