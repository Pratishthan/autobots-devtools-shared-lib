# ABOUTME: Tests for MCP tool adapter — creates namespaced LangChain tool placeholders.
# ABOUTME: Validates naming, auth extraction, error messages, and MCP delegation.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.mcp.session_manager import McpSessionManager
from autobots_devtools_shared_lib.dynagent.mcp.tool_adapter import create_mcp_placeholder


@pytest.fixture(autouse=True)
def _reset():
    McpServerRegistry.reset()
    McpSessionManager.reset()
    yield
    McpSessionManager.reset()
    McpServerRegistry.reset()


@pytest.fixture
def _register_test_server():
    reg = McpServerRegistry.instance()
    reg.register(
        McpServerConfig(
            name="test_mcp",
            transport=McpTransport.STDIO,
            command="echo",
            auth_state_key="test_mcp",
        )
    )


class TestCreateMcpPlaceholder:
    def test_tool_name_is_namespaced(self):
        tool = create_mcp_placeholder("atlassian", "create_issue")
        assert tool.name == "atlassian.create_issue"

    def test_tool_has_description(self):
        tool = create_mcp_placeholder("atlassian", "create_issue")
        assert "atlassian.create_issue" in tool.description

    def test_tool_is_coroutine(self):
        tool = create_mcp_placeholder("atlassian", "create_issue")
        assert tool.coroutine is not None

    @patch("autobots_devtools_shared_lib.dynagent.mcp.tool_adapter.McpSessionManager")
    async def test_invocation_reads_auth_from_mcp_auth(self, mock_mgr_cls, _register_test_server):
        """Tool should read token from state['mcp_auth']['test_mcp']."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.content = [MagicMock(text="result-text", type="text")]
        mock_result.isError = False
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_mgr = MagicMock()
        mock_mgr.get_or_create = AsyncMock(return_value=mock_session)
        mock_mgr_cls.instance.return_value = mock_mgr

        tool = create_mcp_placeholder("test_mcp", "do_thing")

        state = {
            "messages": [],
            "session_id": "s1",
            "mcp_auth": {"test_mcp": "my-token"},
        }
        _result = await tool.coroutine(state=state, tool_input={"key": "value"})

        mock_mgr.get_or_create.assert_called_once_with("test_mcp", "s1", "my-token")
        mock_session.call_tool.assert_called_once_with("do_thing", {"key": "value"})

    @patch("autobots_devtools_shared_lib.dynagent.mcp.tool_adapter.McpSessionManager")
    async def test_missing_auth_returns_friendly_error(self, mock_mgr_cls, _register_test_server):
        """When mcp_auth is missing, return an error message for the LLM."""
        tool = create_mcp_placeholder("test_mcp", "do_thing")

        state = {
            "messages": [],
            "session_id": "s1",
            # No mcp_auth
        }
        result = await tool.coroutine(state=state)

        assert "Authentication required" in result
        assert "test_mcp" in result
