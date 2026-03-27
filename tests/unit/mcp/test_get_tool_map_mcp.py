# ABOUTME: Tests for MCP integration in get_tool_map().
# ABOUTME: Validates dotted tool names resolve to MCP placeholders, non-dotted unchanged.

import pytest

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    get_tool_map,
)
from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.tools.tool_registry import _reset_usecase_tools


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    _reset_agent_config()
    _reset_usecase_tools()
    McpServerRegistry.reset()
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
        lambda: tmp_path,
    )
    yield
    _reset_agent_config()
    _reset_usecase_tools()
    McpServerRegistry.reset()


def _write_agents_yaml(tmp_path, content: str):
    (tmp_path / "agents.yaml").write_text(content)
    (tmp_path / "prompts").mkdir(exist_ok=True)
    (tmp_path / "prompts" / "test.md").write_text("You are a test agent.")


class TestGetToolMapMcp:
    def test_dotted_tool_name_creates_mcp_placeholder(self, tmp_path):
        """Tool name with '.' should resolve to an MCP placeholder."""
        McpServerRegistry.instance().register(
            McpServerConfig(name="atlas", transport=McpTransport.STDIO, command="echo")
        )
        _write_agents_yaml(
            tmp_path,
            "mcp_servers:\n  atlas:\n    enabled: true\n"
            "agents:\n  test_agent:\n    prompt: test\n    tools: [atlas.create_issue, handoff]\n",
        )
        tool_map = get_tool_map()
        names = [t.name for t in tool_map["test_agent"]]
        assert "atlas.create_issue" in names
        assert "handoff" in names

    def test_non_dotted_tools_still_resolve_normally(self, tmp_path):
        """Non-dotted tool names should resolve from the existing tool pool."""
        _write_agents_yaml(
            tmp_path,
            "agents:\n  test_agent:\n    prompt: test\n    tools: [handoff]\n",
        )
        tool_map = get_tool_map()
        names = [t.name for t in tool_map["test_agent"]]
        assert "handoff" in names

    def test_dotted_tool_unknown_server_raises(self, tmp_path):
        """Dotted tool referencing unregistered server should raise."""
        _write_agents_yaml(
            tmp_path,
            "agents:\n  test_agent:\n    prompt: test\n    tools: [unknown.do_thing]\n",
        )
        with pytest.raises(KeyError, match="unknown"):
            get_tool_map()

    def test_mixed_mcp_and_native_tools(self, tmp_path):
        """Agent with both MCP and native tools should resolve both."""
        McpServerRegistry.instance().register(
            McpServerConfig(name="jira", transport=McpTransport.STDIO, command="echo")
        )
        _write_agents_yaml(
            tmp_path,
            "mcp_servers:\n  jira:\n    enabled: true\n"
            "agents:\n  test_agent:\n    prompt: test\n    tools: [jira.search, handoff, get_agent_list]\n",
        )
        tool_map = get_tool_map()
        names = [t.name for t in tool_map["test_agent"]]
        assert "jira.search" in names
        assert "handoff" in names
        assert "get_agent_list" in names
