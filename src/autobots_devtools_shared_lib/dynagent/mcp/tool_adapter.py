# ABOUTME: Wraps MCP tools as namespaced LangChain StructuredTools.
# ABOUTME: Creates lazy placeholder tools that connect to MCP servers on first invocation.

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.mcp.session_manager import McpSessionManager

logger = get_logger(__name__)


def _extract_text(call_result: Any) -> str:
    """Extract text content from a CallToolResult."""
    if call_result.isError:
        parts = [c.text for c in call_result.content if hasattr(c, "text")]
        return f"MCP tool error: {' '.join(parts)}" if parts else "MCP tool returned an error"

    parts = [content.text for content in call_result.content if hasattr(content, "text")]
    return "\n".join(parts) if parts else "MCP tool returned no text content"


def create_mcp_placeholder(server_name: str, tool_name: str) -> StructuredTool:
    """Create a LangChain tool placeholder that delegates to an MCP server on invocation.

    The tool is named '<server_name>.<tool_name>' (e.g., 'atlassian.create_issue').
    On first call, it lazily connects to the MCP server using the session's auth token.
    """
    full_name = f"{server_name}.{tool_name}"

    async def _invoke(state: dict[str, Any] | None = None, **kwargs: Any) -> str:
        state = state or {}
        session_id = state.get("session_id", "default")

        # Read auth token from state["mcp_auth"][auth_state_key]
        config = McpServerRegistry.instance().get(server_name)
        mcp_auth: dict[str, str] = state.get("mcp_auth", {})
        auth_token = mcp_auth.get(config.auth_state_key) if config.auth_state_key else None

        if config.auth_state_key and not auth_token:
            return (
                f"Authentication required for {server_name}. "
                f"Please provide your token (expected in mcp_auth['{config.auth_state_key}'])."
            )

        try:
            session = await McpSessionManager.instance().get_or_create(
                server_name, session_id, auth_token
            )
            # Extract tool_input from kwargs if passed, otherwise use remaining kwargs
            tool_input = kwargs.pop("tool_input", None) or kwargs or None
            result = await session.call_tool(tool_name, tool_input)  # type: ignore[union-attr]
            return _extract_text(result)
        except Exception as e:
            logger.exception("MCP tool invocation failed: %s", full_name)
            return f"MCP tool '{full_name}' failed: {e}"

    return StructuredTool.from_function(
        coroutine=_invoke,
        func=lambda **_kwargs: None,  # sync stub — async-only tool
        name=full_name,
        description=f"MCP tool: {full_name} (connects to {server_name} MCP server)",
    )
