# ABOUTME: Unit tests for the /tools access heuristic, grouping, and degrade path.
# ABOUTME: load_mcp_tools is monkeypatched with fake tool objects (no real MCP server).

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import autobots_devtools_shared_lib.dynagent.api.resources.tools as tools_mod
from autobots_devtools_shared_lib.dynagent.api.resources.tools import (
    build_tools_router,
    tool_access,
)


class FakeTool:
    def __init__(self, name, description="", args=None):
        self.name = name
        self.description = description
        self.args = args or {}


@pytest.mark.parametrize(
    "name,expected",
    [
        ("github__get_issue", "READ"),
        ("github__create_issue", "WRITE"),
        ("github__list_repos", "READ"),
        ("jira__update_ticket", "WRITE"),
        ("jira__delete_board", "WRITE"),
        ("search", "READ"),
    ],
)
def test_tool_access_heuristic(name, expected):
    assert tool_access(name) == expected


def test_group_mcp_tools_groups_by_server(monkeypatch):
    def fake_load(server_names, _config):
        (server,) = server_names
        return [FakeTool(f"{server}__get_x", "reads x", {"id": {}})]

    monkeypatch.setattr(tools_mod, "load_mcp_tools", fake_load)
    meta = SimpleNamespace(mcp_servers_config={"github": {}, "jira": {}})
    servers, warnings = tools_mod.group_mcp_tools(meta)
    names = {s["server"] for s in servers}
    assert names == {"github", "jira"}
    gh = next(s for s in servers if s["server"] == "github")
    assert gh["tools"][0]["name"] == "get_x"
    assert gh["tools"][0]["params"] == ["id"]
    assert gh["tools"][0]["access"] == "READ"
    assert warnings == []


def test_group_mcp_tools_degrades_on_unreachable_server(monkeypatch):
    def fake_load(server_names, _config):
        (server,) = server_names
        if server == "broken":
            raise RuntimeError("connection refused")
        return [FakeTool(f"{server}__ok")]

    monkeypatch.setattr(tools_mod, "load_mcp_tools", fake_load)
    meta = SimpleNamespace(mcp_servers_config={"good": {}, "broken": {}})
    servers, warnings = tools_mod.group_mcp_tools(meta)
    good = next(s for s in servers if s["server"] == "good")
    broken = next(s for s in servers if s["server"] == "broken")
    assert good["tools"][0]["name"] == "ok"
    assert broken["tools"] == []
    assert any("broken" in w for w in warnings)


def test_tools_endpoint_empty_config_returns_empty(monkeypatch):
    meta = SimpleNamespace(mcp_servers_config={})
    app = FastAPI()
    app.include_router(build_tools_router(meta))
    body = TestClient(app).get("/tools").json()
    assert body == {"servers": [], "warnings": []}
