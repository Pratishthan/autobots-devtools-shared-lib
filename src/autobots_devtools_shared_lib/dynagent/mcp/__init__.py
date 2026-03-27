# ABOUTME: Public API for the MCP integration layer.
# ABOUTME: Provides MCP client management, tool adapters, and server registration.

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.mcp.session_manager import McpSessionManager
from autobots_devtools_shared_lib.dynagent.mcp.tool_adapter import create_mcp_placeholder


def register_mcp_servers(configs: list[McpServerConfig]) -> None:
    """Register use-case MCP server configs. Call once at startup before create_base_agent()."""
    registry = McpServerRegistry.instance()
    for config in configs:
        registry.register(config)


__all__ = [
    "McpServerConfig",
    "McpServerRegistry",
    "McpSessionManager",
    "McpTransport",
    "create_mcp_placeholder",
    "register_mcp_servers",
]
