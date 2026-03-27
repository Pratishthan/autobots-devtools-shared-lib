# ABOUTME: Tests for McpServerRegistry singleton.
# ABOUTME: Validates bundled servers, usecase registration, override behavior, and reset.

import pytest

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset registry before and after each test."""
    McpServerRegistry.reset()
    yield
    McpServerRegistry.reset()


class TestMcpServerRegistry:
    def test_instance_is_singleton(self):
        a = McpServerRegistry.instance()
        b = McpServerRegistry.instance()
        assert a is b

    def test_bundled_atlassian_is_available(self):
        reg = McpServerRegistry.instance()
        cfg = reg.get("atlassian")
        assert cfg.name == "atlassian"
        assert cfg.transport == McpTransport.STDIO
        assert cfg.command == "npx"

    def test_list_servers_includes_bundled(self):
        reg = McpServerRegistry.instance()
        assert "atlassian" in reg.list_servers()

    def test_get_unknown_server_raises(self):
        reg = McpServerRegistry.instance()
        with pytest.raises(KeyError, match="no_such_server"):
            reg.get("no_such_server")

    def test_register_usecase_server(self):
        reg = McpServerRegistry.instance()
        custom = McpServerConfig(
            name="custom",
            transport=McpTransport.STREAMABLE_HTTP,
            url="https://example.com",
        )
        reg.register(custom)
        assert reg.get("custom") is custom
        assert "custom" in reg.list_servers()

    def test_usecase_overrides_bundled(self):
        """Use-case registration with the same name overrides the bundled config."""
        reg = McpServerRegistry.instance()
        override = McpServerConfig(
            name="atlassian",
            transport=McpTransport.STREAMABLE_HTTP,
            url="https://override.example.com",
            auth_state_key="atlassian",
        )
        reg.register(override)
        cfg = reg.get("atlassian")
        assert cfg.transport == McpTransport.STREAMABLE_HTTP
        assert cfg.url == "https://override.example.com"

    def test_reset_clears_singleton(self):
        reg1 = McpServerRegistry.instance()
        McpServerRegistry.reset()
        reg2 = McpServerRegistry.instance()
        assert reg1 is not reg2

    def test_register_does_not_pollute_bundled(self):
        """Registering a usecase server must not modify the bundled dict."""
        reg = McpServerRegistry.instance()
        custom = McpServerConfig(name="custom", transport=McpTransport.STDIO, command="echo")
        reg.register(custom)
        # Bundled dict should not contain custom
        assert "custom" not in reg._bundled
