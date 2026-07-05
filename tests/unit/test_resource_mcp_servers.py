# ABOUTME: TestClient coverage for /mcp-servers: list + display-only connected pref.
# ABOUTME: group_mcp_tools is monkeypatched to supply tool_count without a real server.

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import autobots_devtools_shared_lib.dynagent.api.resources.mcp_servers as mcp_mod
from autobots_devtools_shared_lib.dynagent.api.resources.mcp_servers import (
    build_mcp_servers_router,
    server_abbr,
)


class FakePrefs:
    def __init__(self) -> None:
        self.kv: dict[tuple[str, str, str], bool] = {}

    async def get(self, user_id, namespace):
        return {k[2]: v for k, v in self.kv.items() if k[0] == user_id and k[1] == namespace}

    async def set(self, user_id, namespace, key, value):
        self.kv[(user_id, namespace, key)] = value


@pytest.mark.parametrize("name,expected", [("github", "GI"), ("jira-cloud", "JC"), ("x", "X")])
def test_server_abbr(name, expected):
    assert server_abbr(name) == expected


@pytest.fixture
def prefs():
    return FakePrefs()


@pytest.fixture
def client(monkeypatch, prefs):
    def fake_group(_meta):
        return [{"server": "github", "tools": [{"name": "a"}, {"name": "b"}]}], []

    monkeypatch.setattr(mcp_mod, "group_mcp_tools", fake_group)
    app = FastAPI()
    app.include_router(
        build_mcp_servers_router(
            meta=SimpleNamespace(mcp_servers_config={"github": {}}),
            prefs_store=prefs,
            user_id_dependency=lambda: "u1",
        )
    )
    return TestClient(app)


def test_list_servers_reports_tool_count(client):
    body = client.get("/mcp-servers").json()
    gh = body["servers"][0]
    assert gh["name"] == "github"
    assert gh["abbr"] == "GI"
    assert gh["tool_count"] == 2
    assert gh["connected"] is False  # default when no pref set


def test_connected_pref_reflected(client, prefs):
    prefs.kv[("u1", "mcp", "github")] = True
    assert client.get("/mcp-servers").json()["servers"][0]["connected"] is True


def test_patch_sets_connected_pref(client, prefs):
    resp = client.patch("/mcp-servers/github", json={"connected": True})
    assert resp.status_code == 200
    assert prefs.kv[("u1", "mcp", "github")] is True


def test_empty_config_returns_empty(monkeypatch, prefs):
    monkeypatch.setattr(mcp_mod, "group_mcp_tools", lambda _m: ([], []))
    app = FastAPI()
    app.include_router(
        build_mcp_servers_router(
            meta=SimpleNamespace(mcp_servers_config={}),
            prefs_store=prefs,
            user_id_dependency=lambda: "u1",
        )
    )
    assert TestClient(app).get("/mcp-servers").json() == {"servers": []}
