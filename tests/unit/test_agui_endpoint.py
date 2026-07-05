# ABOUTME: Smoke test for mount_agui_endpoint — mounts a RailAGUIAgent at the given path.
# ABOUTME: Uses a mock graph; asserts the route registers and RailAGUIAgent gets rail kwargs.

from unittest.mock import MagicMock

import pytest

pytest.importorskip("copilotkit")

_MODULE = "autobots_devtools_shared_lib.dynagent.ui.agui_endpoint"


def test_mounts_route_and_builds_rail_agent():
    from unittest.mock import patch

    from fastapi import FastAPI

    from autobots_devtools_shared_lib.dynagent.ui.agui_endpoint import mount_agui_endpoint
    from autobots_devtools_shared_lib.dynagent.ui.rail_stream import RailAGUIAgent

    app = FastAPI()
    graph = MagicMock(name="graph")

    with patch(f"{_MODULE}.RailAGUIAgent", wraps=RailAGUIAgent) as spy:
        mount_agui_endpoint(
            app,
            graph,
            graph_id="assistant",
            mcp_servers={"github"},
            main_agent_name="assistant",
            path="/agent",
        )

    assert "/agent" in {route.path for route in app.routes}
    assert spy.call_args.kwargs["mcp_servers"] == {"github"}
    assert spy.call_args.kwargs["main_agent_name"] == "assistant"
