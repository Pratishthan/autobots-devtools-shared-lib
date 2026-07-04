# ABOUTME: Smoke tests for the deep-engine CopilotKit/AG-UI FastAPI app factory.
# ABOUTME: Confirms create_copilotkit_app wraps create_base_deepagent and mounts the AG-UI route.

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("copilotkit")

_MODULE = "autobots_devtools_shared_lib.dynagent.ui.copilotkit_server"


@pytest.fixture
def mock_graph():
    graph = MagicMock(name="compiled_graph")
    graph.with_config.return_value = graph
    return graph


@patch(f"{_MODULE}.get_langfuse_handler", return_value=None)
@patch(f"{_MODULE}.create_base_deepagent")
def test_mounts_agui_route(mock_create_deep, _mock_lf, mock_graph):
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_deep.return_value = mock_graph
    app = create_copilotkit_app(agent_name="assistant", path="/agent")

    mock_create_deep.assert_called_once()
    assert "/agent" in {route.path for route in app.routes}


@patch(f"{_MODULE}.get_langfuse_handler", return_value=None)
@patch(f"{_MODULE}.create_base_deepagent")
def test_passes_copilotkit_and_collapse_middleware(mock_create_deep, _mock_lf, mock_graph):
    from autobots_devtools_shared_lib.dynagent.ui import copilotkit_server

    mock_create_deep.return_value = mock_graph
    copilotkit_server.create_copilotkit_app(agent_name="assistant")

    middleware = mock_create_deep.call_args.kwargs["middleware"]
    names = [type(m).__name__ for m in middleware]
    # CopilotKitMiddleware first, collapse middleware inner (after it)
    assert names[0] == "CopilotKitMiddleware"
    assert middleware[-1] is copilotkit_server.collapse_system_messages
