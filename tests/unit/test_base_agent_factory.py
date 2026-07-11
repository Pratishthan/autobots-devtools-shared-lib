# ABOUTME: Unit tests for the classic agent engine factory (create_base_agent).
# ABOUTME: Verifies caller middleware is appended after the injected-agent + summarisation stack.

from unittest.mock import MagicMock, patch

import pytest
from langchain.agents.middleware import SummarizationMiddleware

import autobots_devtools_shared_lib.dynagent.agents.base_agent as ba
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent


@pytest.fixture
def patched():
    # SummarizationMiddleware's fractional trigger reads the model's token profile.
    model = MagicMock(name="model")
    model.profile = {"max_input_tokens": 200_000}
    with (
        patch.object(ba.AgentMeta, "instance", return_value=MagicMock()),
        patch.object(ba, "get_default_agent", return_value="coordinator"),
        patch.object(ba, "lm", return_value=model),
        patch.object(ba, "get_all_tools", return_value=["tool_a"]),
        patch.object(ba, "create_agent", return_value="GRAPH") as mock_ca,
    ):
        yield mock_ca


def test_default_middleware_stack_is_inject_agent_then_summarisation(patched):
    ba.create_base_agent()

    middleware = patched.call_args.kwargs["middleware"]
    assert middleware[0] is ba.inject_agent_async
    assert isinstance(middleware[1], SummarizationMiddleware)
    assert len(middleware) == 2


def test_caller_middleware_appended_after_existing(patched):
    extra_one = MagicMock(name="extra_one")
    extra_two = MagicMock(name="extra_two")

    ba.create_base_agent(middleware=[extra_one, extra_two])

    middleware = patched.call_args.kwargs["middleware"]
    assert middleware[0] is ba.inject_agent_async
    assert isinstance(middleware[1], SummarizationMiddleware)
    assert middleware[2] is extra_one
    assert middleware[3] is extra_two


def test_sync_mode_keeps_caller_middleware_last(patched):
    extra = MagicMock(name="extra")

    ba.create_base_agent(sync_mode=True, middleware=[extra])

    middleware = patched.call_args.kwargs["middleware"]
    assert middleware[0] is ba.inject_agent_sync
    assert middleware[-1] is extra


def test_state_schema_and_name_unchanged(patched):
    ba.create_base_agent(middleware=[MagicMock()])

    kwargs = patched.call_args.kwargs
    assert kwargs["state_schema"] is Dynagent
    assert kwargs["name"] == "coordinator"
