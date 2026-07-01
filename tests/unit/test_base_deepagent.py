# ABOUTME: Unit tests for the deep-agent engine factory.
# ABOUTME: Verifies create_base_deepagent wires model/tools/prompt/state into create_deep_agent.

from unittest.mock import MagicMock, patch

import pytest

import autobots_devtools_shared_lib.dynagent.agents.base_deepagent as bd
from autobots_devtools_shared_lib.dynagent.models.deep_state import DynaDeepAgent


@pytest.fixture
def fake_meta():
    meta = MagicMock()
    meta.prompt_map = {"assistant": "You are an assistant writing {language}."}
    meta.tool_map = {"assistant": ["tool_a", "tool_b"]}
    meta.input_schema_map = {"assistant": {}}
    meta.output_schema_map = {"assistant": None}
    return meta


@pytest.fixture
def patched(fake_meta):
    with (
        patch.object(bd.AgentMeta, "instance", return_value=fake_meta),
        patch.object(bd, "get_default_agent", return_value="assistant"),
        patch.object(bd, "lm", return_value="MODEL"),
        patch.object(bd, "create_deep_agent", return_value="GRAPH") as mock_cda,
    ):
        yield mock_cda


def test_returns_compiled_graph_from_create_deep_agent(patched):
    result = bd.create_base_deepagent()
    assert result == "GRAPH"
    patched.assert_called_once()


def test_wires_model_tools_state_and_name(patched):
    bd.create_base_deepagent(initial_agent_name="assistant")
    kwargs = patched.call_args.kwargs
    assert kwargs["model"] == "MODEL"
    assert kwargs["tools"] == ["tool_a", "tool_b"]
    assert kwargs["state_schema"] is DynaDeepAgent
    assert kwargs["name"] == "assistant"
    assert kwargs["checkpointer"] is not None


def test_prompt_values_substituted_into_system_prompt(patched):
    bd.create_base_deepagent(prompt_values={"language": "java"})
    kwargs = patched.call_args.kwargs
    assert kwargs["system_prompt"] == "You are an assistant writing java."


def test_unknown_placeholder_resolves_to_empty(patched, fake_meta):
    fake_meta.prompt_map = {"assistant": "lang={language} extra={unknown}"}
    bd.create_base_deepagent(prompt_values={"language": "java"})
    kwargs = patched.call_args.kwargs
    assert kwargs["system_prompt"] == "lang=java extra="
