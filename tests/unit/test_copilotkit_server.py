# ABOUTME: Smoke test for the generic CopilotKit/AG-UI FastAPI app factory.
# ABOUTME: Confirms create_copilotkit_app builds and mounts the AG-UI route.

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("copilotkit")


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

    mock_create_base_agent.assert_called_once()
    paths = {route.path for route in app.routes}
    assert "/agent" in paths


@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_create_copilotkit_app_default_args(mock_create_base_agent, mock_graph):
    """Defaults mount the derived agent at /agent."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph

    app = create_copilotkit_app()

    paths = {route.path for route in app.routes}
    assert "/agent" in paths


@patch("ag_ui_langgraph.add_langgraph_fastapi_endpoint")
@patch("copilotkit.LangGraphAGUIAgent")
@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.get_default_agent")
@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_builds_copilotkit_graph_and_derives_name(
    mock_create_base_agent, mock_get_default_agent, mock_agui_agent, mock_add_endpoint, mock_graph
):
    """When agent_name is omitted, the graph id is derived and copilotkit=True is passed."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph
    mock_get_default_agent.return_value = "myagent"

    create_copilotkit_app()

    # create_base_agent was asked for the CopilotKit-flavored graph.
    assert mock_create_base_agent.call_args.kwargs.get("copilotkit") is True
    # The AG-UI agent is named after the derived default agent.
    assert mock_agui_agent.call_args.kwargs.get("name") == "myagent"


@patch("ag_ui_langgraph.add_langgraph_fastapi_endpoint")
@patch("copilotkit.LangGraphAGUIAgent")
@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.get_default_agent")
@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_falls_back_to_dynagent_when_no_default(
    mock_create_base_agent, mock_get_default_agent, mock_agui_agent, mock_add_endpoint, mock_graph
):
    """With no configured default agent, the graph id falls back to 'dynagent'."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph
    mock_get_default_agent.return_value = None

    create_copilotkit_app()

    assert mock_agui_agent.call_args.kwargs.get("name") == "dynagent"
