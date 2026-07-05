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
