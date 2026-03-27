# ABOUTME: Bundled Atlassian MCP server configuration.
# ABOUTME: Provides Jira, Confluence, etc. via the Atlassian MCP server.

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport

ATLASSIAN_MCP = McpServerConfig(
    name="atlassian",
    transport=McpTransport.STDIO,
    command="npx",
    args=["@anthropic/atlassian-mcp-server"],
    auth_state_key="atlassian",
)
