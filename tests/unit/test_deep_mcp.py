# ABOUTME: Unit tests for config-driven MCP tool loading (stubbed MultiServerMCPClient).
# ABOUTME: Covers name prefixing, empty short-circuit, and the event-loop-aware bridge.

import sys
from types import SimpleNamespace

from autobots_devtools_shared_lib.dynagent.agents.deep_mcp import _run_coro, load_mcp_tools


def _install_fake_adapters(monkeypatch, tools_by_server):
    class FakeClient:
        def __init__(self, connections):
            self.connections = connections

        async def get_tools(self, server_name=None):
            return tools_by_server[server_name]

    fake_client_module = SimpleNamespace(MultiServerMCPClient=FakeClient)
    monkeypatch.setitem(
        sys.modules, "langchain_mcp_adapters", SimpleNamespace(client=fake_client_module)
    )
    monkeypatch.setitem(sys.modules, "langchain_mcp_adapters.client", fake_client_module)


def test_empty_server_list_returns_empty_without_client():
    assert load_mcp_tools([], {"atlassian": {"transport": "stdio"}}) == []


def test_tools_loaded_and_name_prefixed(monkeypatch):
    _install_fake_adapters(
        monkeypatch,
        {
            "atlassian": [SimpleNamespace(name="search"), SimpleNamespace(name="create_issue")],
            "github": [SimpleNamespace(name="search")],
        },
    )
    tools = load_mcp_tools(
        ["atlassian", "github"],
        {"atlassian": {"transport": "stdio"}, "github": {"transport": "stdio"}},
    )
    assert [t.name for t in tools] == [
        "atlassian__search",
        "atlassian__create_issue",
        "github__search",
    ]


def test_only_referenced_servers_are_connected(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, connections):
            seen["connections"] = connections

        async def get_tools(self, server_name=None):
            return []

    fake_client_module = SimpleNamespace(MultiServerMCPClient=FakeClient)
    monkeypatch.setitem(
        sys.modules, "langchain_mcp_adapters", SimpleNamespace(client=fake_client_module)
    )
    monkeypatch.setitem(sys.modules, "langchain_mcp_adapters.client", fake_client_module)
    load_mcp_tools(["a"], {"a": {"transport": "stdio"}, "b": {"transport": "stdio"}})
    assert set(seen["connections"]) == {"a"}


def test_run_coro_without_running_loop():
    async def coro():
        return 42

    assert _run_coro(coro()) == 42


async def test_run_coro_inside_running_loop():
    async def coro():
        return 42

    assert _run_coro(coro()) == 42
