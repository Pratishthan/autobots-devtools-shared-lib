# ABOUTME: Composition smoke test for create_agui_app using a stub agent factory (no LLM).
# ABOUTME: Asserts /agent + all resource routes + /health mount and CORS is configured.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("copilotkit")

_MODULE = "autobots_devtools_shared_lib.dynagent.ui.agui_app"


class FakeThreadStore:
    async def list(self, user_id, q=None):
        return []

    async def create(self, user_id, title="New chat"):
        return {
            "id": "t1",
            "user_id": user_id,
            "title": title,
            "created_at": None,
            "updated_at": None,
        }

    async def get(self, thread_id):
        return None

    async def rename(self, thread_id, title):
        pass

    async def delete(self, thread_id):
        pass

    async def touch(self, thread_id):
        pass


class FakePrefs:
    async def get(self, user_id, namespace):
        return {}

    async def set(self, user_id, namespace, key, value):
        pass


@patch(f"{_MODULE}.get_langfuse_handler", return_value=None)
def test_mounts_both_planes_and_health(_mock_lf):
    from autobots_devtools_shared_lib.dynagent.ui.agui_app import create_agui_app

    fake_meta = SimpleNamespace(skills_map={}, mcp_servers_config={})
    stub_graph = MagicMock(name="graph")
    stub_graph.with_config.return_value = stub_graph

    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.agent_meta.AgentMeta.instance",
        return_value=fake_meta,
    ):
        app = create_agui_app(
            checkpointer=MagicMock(),
            thread_store=FakeThreadStore(),
            prefs_store=FakePrefs(),
            backend=object(),
            user_id_dependency=lambda: "u1",
            agent_name="assistant",
            agent_factory=lambda **_kwargs: stub_graph,
        )

    paths = {route.path for route in app.routes}
    assert "/agent" in paths
    assert "/threads" in paths
    assert "/skills" in paths
    assert "/tools" in paths
    assert "/mcp-servers" in paths
    assert "/health" in paths


@patch(f"{_MODULE}.get_langfuse_handler", return_value=None)
def test_agent_factory_receives_copilotkit_and_collapse_middleware(_mock_lf):
    from autobots_devtools_shared_lib.dynagent.ui import agui_app

    fake_meta = SimpleNamespace(skills_map={}, mcp_servers_config={})
    captured = {}

    def stub_factory(**kwargs):
        captured.update(kwargs)
        g = MagicMock()
        g.with_config.return_value = g
        return g

    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.agent_meta.AgentMeta.instance",
        return_value=fake_meta,
    ):
        agui_app.create_agui_app(
            checkpointer=MagicMock(),
            thread_store=FakeThreadStore(),
            prefs_store=FakePrefs(),
            backend=object(),
            user_id_dependency=lambda: "u1",
            agent_name="assistant",
            agent_factory=stub_factory,
        )

    mw = captured["middleware"]
    assert type(mw[0]).__name__ == "CopilotKitMiddleware"
    assert mw[-1] is agui_app.collapse_system_messages


@patch(f"{_MODULE}.get_langfuse_handler", return_value=None)
def test_thread_creation_policy_reaches_the_threads_route(_mock_lf):
    """A domain narrows POST /threads through create_agui_app, without owning the router."""
    from fastapi.testclient import TestClient
    from pydantic import BaseModel, Field

    from autobots_devtools_shared_lib.dynagent.ui.agui_app import create_agui_app

    class TicketBody(BaseModel):
        title: str = Field(min_length=1)
        jira_number: str = Field(min_length=1)

    seeded = []

    async def on_thread_created(record, body):
        seeded.append((record["id"], body.jira_number))

    fake_meta = SimpleNamespace(skills_map={}, mcp_servers_config={})
    stub_graph = MagicMock(name="graph")
    stub_graph.with_config.return_value = stub_graph

    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.agent_meta.AgentMeta.instance",
        return_value=fake_meta,
    ):
        app = create_agui_app(
            checkpointer=MagicMock(),
            thread_store=FakeThreadStore(),
            prefs_store=FakePrefs(),
            backend=object(),
            user_id_dependency=lambda: "u1",
            agent_name="assistant",
            agent_factory=lambda **_kwargs: stub_graph,
            create_body_model=TicketBody,
            on_thread_created=on_thread_created,
        )

    client = TestClient(app)
    assert client.post("/threads", json={"title": "untethered"}).status_code == 422
    assert seeded == []

    resp = client.post("/threads", json={"title": "MER-1 LLD", "jira_number": "MER-1"})
    assert resp.status_code == 200
    assert seeded == [("t1", "MER-1")]


@patch(f"{_MODULE}.get_langfuse_handler", return_value=None)
def test_composes_with_the_classic_agent_factory(_mock_lf, bro_registered, monkeypatch):
    """ADR-0003's seam: the classic engine composes on the AG-UI plane.

    This is the risk spike — CopilotKitMiddleware has only ever run against deep-agent
    state, and here it is handed the classic engine's Dynagent schema. Nothing is stubbed
    below create_agui_app but the LLM credentials, so a middleware that rejects the classic
    state schema fails here rather than in the Canvas.
    """
    from langgraph.checkpoint.memory import InMemorySaver
    from starlette.middleware.cors import CORSMiddleware

    from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent
    from autobots_devtools_shared_lib.dynagent.ui.agui_app import create_agui_app

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-used-no-llm-call")

    app = create_agui_app(
        checkpointer=InMemorySaver(),
        thread_store=FakeThreadStore(),
        prefs_store=FakePrefs(),
        backend=object(),
        user_id_dependency=lambda: "u1",
        agent_name="coordinator",
        agent_factory=create_base_agent,
    )

    paths = {route.path for route in app.routes}
    assert {"/agent", "/threads", "/skills", "/tools", "/mcp-servers", "/health"} <= paths
    assert any(m.cls is CORSMiddleware for m in app.user_middleware)
