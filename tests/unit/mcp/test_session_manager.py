# ABOUTME: Tests for McpSessionManager — per-session MCP client lifecycle.
# ABOUTME: Uses mock MCP clients to test caching, cleanup, and error handling.

from unittest.mock import AsyncMock, patch

import pytest

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.mcp.session_manager import McpSessionManager


@pytest.fixture(autouse=True)
def _reset():
    McpServerRegistry.reset()
    McpSessionManager.reset()
    yield
    McpSessionManager.reset()
    McpServerRegistry.reset()


@pytest.fixture
def stdio_server():
    """Register a test stdio server."""
    reg = McpServerRegistry.instance()
    cfg = McpServerConfig(
        name="test_server",
        transport=McpTransport.STDIO,
        command="echo",
        args=["hello"],
        auth_state_key="test_server",
    )
    reg.register(cfg)
    return cfg


class TestMcpSessionManager:
    async def test_instance_is_singleton(self):
        a = McpSessionManager.instance()
        b = McpSessionManager.instance()
        assert a is b

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.session_manager.McpSessionManager._create_connection"
    )
    async def test_get_or_create_caches_connection(self, mock_create, stdio_server):
        mock_session = AsyncMock()
        mock_create.return_value = mock_session

        mgr = McpSessionManager.instance()
        first = await mgr.get_or_create("test_server", "session-1", "token-abc")
        second = await mgr.get_or_create("test_server", "session-1", "token-abc")

        assert first is second
        assert mock_create.call_count == 1

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.session_manager.McpSessionManager._create_connection"
    )
    async def test_different_sessions_get_different_connections(self, mock_create, stdio_server):
        mock_create.side_effect = [AsyncMock(), AsyncMock()]

        mgr = McpSessionManager.instance()
        first = await mgr.get_or_create("test_server", "session-1", "token-a")
        second = await mgr.get_or_create("test_server", "session-2", "token-b")

        assert first is not second
        assert mock_create.call_count == 2

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.session_manager.McpSessionManager._create_connection"
    )
    async def test_close_session_removes_connections(self, mock_create, stdio_server):
        mock_session = AsyncMock()
        mock_create.return_value = mock_session

        mgr = McpSessionManager.instance()
        await mgr.get_or_create("test_server", "session-1", "token-abc")
        await mgr.close_session("session-1")

        # Next call should create a new connection
        mock_create.return_value = AsyncMock()
        new_conn = await mgr.get_or_create("test_server", "session-1", "token-abc")
        assert new_conn is not mock_session

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.session_manager.McpSessionManager._create_connection"
    )
    async def test_close_all_clears_everything(self, mock_create, stdio_server):
        mock_create.side_effect = [AsyncMock(), AsyncMock()]

        mgr = McpSessionManager.instance()
        await mgr.get_or_create("test_server", "session-1", "token-a")
        await mgr.get_or_create("test_server", "session-2", "token-b")
        await mgr.close_all()

        assert len(mgr._connections) == 0

    async def test_get_or_create_unknown_server_raises(self):
        mgr = McpSessionManager.instance()
        with pytest.raises(KeyError, match="unknown_server"):
            await mgr.get_or_create("unknown_server", "session-1", None)
