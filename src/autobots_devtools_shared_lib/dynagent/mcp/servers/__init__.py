# ABOUTME: Bundled MCP server definitions shipped with shared-lib.
# ABOUTME: Auto-registers all bundled servers into McpServerRegistry.

from autobots_devtools_shared_lib.dynagent.mcp.servers.atlassian import ATLASSIAN_MCP

BUNDLED_SERVERS = [ATLASSIAN_MCP]

__all__ = ["BUNDLED_SERVERS"]
