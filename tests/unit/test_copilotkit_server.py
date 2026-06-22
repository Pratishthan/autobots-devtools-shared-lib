# ABOUTME: Smoke test for the generic CopilotKit/AG-UI FastAPI app factory.
# ABOUTME: Confirms create_copilotkit_app builds and mounts the AG-UI route.

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_graph():
    """A stand-in compiled graph whose .with_config returns itself."""
    graph = MagicMock(name="compiled_graph")
    graph.with_config.return_value = graph
    return graph


@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_create_copilotkit_app_mounts_agui_route(mock_create_base_agent, mock_graph):
    """The factory returns a FastAPI app with the AG-UI route registered."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph

    app = create_copilotkit_app(agent_name="coordinator", path="/agent")

    # Built the graph exactly once via the shared factory.
    mock_create_base_agent.assert_called_once()

    # The AG-UI endpoint is registered on the app under the requested path.
    paths = {route.path for route in app.routes}
    assert "/agent" in paths


@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_create_copilotkit_app_default_args(mock_create_base_agent, mock_graph):
    """Defaults mount the coordinator agent at /agent."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph

    app = create_copilotkit_app()

    paths = {route.path for route in app.routes}
    assert "/agent" in paths
