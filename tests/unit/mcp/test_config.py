# ABOUTME: Tests for MCP config types: McpTransport enum and McpServerConfig dataclass.
# ABOUTME: Validates construction, defaults, and YAML config loading.


from autobots_devtools_shared_lib.dynagent.mcp.config import (
    McpServerConfig,
    McpTransport,
    load_mcp_config,
)


class TestMcpTransport:
    def test_stdio_value(self):
        assert McpTransport.STDIO.value == "stdio"

    def test_streamable_http_value(self):
        assert McpTransport.STREAMABLE_HTTP.value == "streamable_http"

    def test_from_string_stdio(self):
        assert McpTransport("stdio") == McpTransport.STDIO

    def test_from_string_streamable_http(self):
        assert McpTransport("streamable_http") == McpTransport.STREAMABLE_HTTP


class TestMcpServerConfig:
    def test_minimal_stdio_config(self):
        cfg = McpServerConfig(
            name="test",
            transport=McpTransport.STDIO,
            command="echo",
        )
        assert cfg.name == "test"
        assert cfg.transport == McpTransport.STDIO
        assert cfg.command == "echo"
        assert cfg.args is None
        assert cfg.env is None
        assert cfg.url is None
        assert cfg.auth_state_key is None

    def test_full_stdio_config(self):
        cfg = McpServerConfig(
            name="atlassian",
            transport=McpTransport.STDIO,
            command="npx",
            args=["@anthropic/atlassian-mcp-server"],
            env={"NODE_ENV": "production"},
            auth_state_key="atlassian",
        )
        assert cfg.args == ["@anthropic/atlassian-mcp-server"]
        assert cfg.env == {"NODE_ENV": "production"}
        assert cfg.auth_state_key == "atlassian"

    def test_streamable_http_config(self):
        cfg = McpServerConfig(
            name="remote",
            transport=McpTransport.STREAMABLE_HTTP,
            url="https://mcp.example.com/api",
            auth_state_key="remote",
        )
        assert cfg.url == "https://mcp.example.com/api"
        assert cfg.transport == McpTransport.STREAMABLE_HTTP


class TestLoadMcpConfig:
    def test_returns_empty_dict_when_no_mcp_servers_section(self, tmp_path, monkeypatch):
        """agents.yaml without mcp_servers section returns {}."""
        agents_yaml = tmp_path / "agents.yaml"
        agents_yaml.write_text("agents:\n  coordinator:\n    prompt: test\n    tools: []\n")
        monkeypatch.setattr(
            "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
            lambda: tmp_path,
        )
        result = load_mcp_config()
        assert result == {}

    def test_loads_mcp_servers_section(self, tmp_path, monkeypatch):
        """agents.yaml with mcp_servers section returns parsed entries."""
        agents_yaml = tmp_path / "agents.yaml"
        agents_yaml.write_text(
            "mcp_servers:\n"
            "  atlassian:\n"
            "    enabled: true\n"
            "agents:\n"
            "  coordinator:\n"
            "    prompt: test\n"
            "    tools: []\n"
        )
        monkeypatch.setattr(
            "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
            lambda: tmp_path,
        )
        result = load_mcp_config()
        assert "atlassian" in result
        assert result["atlassian"]["enabled"] is True

    def test_loads_mcp_server_with_overrides(self, tmp_path, monkeypatch):
        """YAML overrides (transport, url) are preserved in the returned dict."""
        agents_yaml = tmp_path / "agents.yaml"
        agents_yaml.write_text(
            "mcp_servers:\n"
            "  atlassian:\n"
            "    enabled: true\n"
            "    transport: streamable_http\n"
            "    url: https://mcp.example.com\n"
            "agents:\n"
            "  coordinator:\n"
            "    prompt: test\n"
            "    tools: []\n"
        )
        monkeypatch.setattr(
            "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
            lambda: tmp_path,
        )
        result = load_mcp_config()
        assert result["atlassian"]["transport"] == "streamable_http"
        assert result["atlassian"]["url"] == "https://mcp.example.com"

    def test_returns_empty_when_agents_yaml_missing(self, tmp_path, monkeypatch):
        """Missing agents.yaml returns {} rather than crashing."""
        monkeypatch.setattr(
            "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
            lambda: tmp_path,
        )
        result = load_mcp_config()
        assert result == {}
