# ABOUTME: Unit tests for the deep-agent engine factory.
# ABOUTME: Verifies create_base_deepagent wires model/tools/prompt/state into create_deep_agent.

from unittest.mock import MagicMock, patch

import pytest

import autobots_devtools_shared_lib.dynagent.agents.base_deepagent as bd
from autobots_devtools_shared_lib.dynagent.middleware.tool_resilience import (
    ToolResilienceMiddleware,
)
from autobots_devtools_shared_lib.dynagent.models.deep_state import DynaDeepAgent


@pytest.fixture
def fake_meta():
    meta = MagicMock()
    meta.prompt_map = {"assistant": "You are an assistant writing {language}."}
    meta.tool_map = {"assistant": ["tool_a", "tool_b"]}
    meta.input_schema_map = {"assistant": {}}
    meta.output_schema_map = {"assistant": None}
    meta.model_map = {"assistant": None}
    meta.skills_map = {"assistant": []}
    meta.memory_map = {"assistant": []}
    meta.interrupt_map = {"assistant": {}}
    meta.permissions_map = {"assistant": []}
    meta.description_map = {"assistant": None}
    meta.mcp_map = {"assistant": []}
    meta.debug_map = {"assistant": False}
    meta.rubric_map = {"assistant": None}
    meta.backend_config = None
    meta.model_profiles = {}
    meta.mcp_servers_config = {}
    return meta


@pytest.fixture
def patched(fake_meta):
    with (
        patch.object(bd.AgentMeta, "instance", return_value=fake_meta),
        patch.object(bd, "get_default_agent", return_value="assistant"),
        patch.object(bd, "resolve_agent_model", return_value="MODEL"),
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


def test_skills_and_memory_forwarded(patched, fake_meta):
    fake_meta.skills_map = {"assistant": ["skills/"]}
    fake_meta.memory_map = {"assistant": ["AGENTS.md"]}
    bd.create_base_deepagent()
    kwargs = patched.call_args.kwargs
    assert kwargs["skills"] == ["skills/"]
    assert kwargs["memory"] == ["AGENTS.md"]


def test_empty_skills_and_memory_forward_none(patched):
    bd.create_base_deepagent()
    kwargs = patched.call_args.kwargs
    assert kwargs["skills"] is None
    assert kwargs["memory"] is None


def test_backend_resolved_from_meta_config(patched, fake_meta, tmp_path):
    fake_meta.backend_config = {"type": "filesystem", "root_dir": str(tmp_path / "ws")}
    bd.create_base_deepagent()
    kwargs = patched.call_args.kwargs
    from deepagents.backends import FilesystemBackend

    assert isinstance(kwargs["backend"], FilesystemBackend)


def test_backend_kwarg_overrides_yaml(patched, fake_meta):
    sentinel = object()
    fake_meta.backend_config = {"type": "state"}
    bd.create_base_deepagent(backend=sentinel)
    assert patched.call_args.kwargs["backend"] is sentinel


def test_resilience_middleware_always_on(patched):
    bd.create_base_deepagent()
    middleware = patched.call_args.kwargs["middleware"]
    assert len(middleware) == 1
    assert isinstance(middleware[0], ToolResilienceMiddleware)


def test_model_resolved_per_agent(patched):
    bd.create_base_deepagent()
    assert patched.call_args.kwargs["model"] == "MODEL"


def test_store_kwarg_reaches_resolve_backend(patched, fake_meta, monkeypatch):
    seen = {}

    def fake_resolve(config, override=None, store=None):
        seen["store"] = store

    monkeypatch.setattr(bd, "resolve_backend", fake_resolve)
    sentinel = object()
    bd.create_base_deepagent(store=sentinel)
    assert seen["store"] is sentinel


def test_output_schema_forwarded_as_response_format(patched, fake_meta):
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    fake_meta.output_schema_map = {"assistant": schema}
    bd.create_base_deepagent()
    assert patched.call_args.kwargs["response_format"] == schema


def test_no_output_schema_forwards_none(patched):
    bd.create_base_deepagent()
    assert patched.call_args.kwargs["response_format"] is None


def test_interrupt_on_forwarded(patched, fake_meta):
    fake_meta.interrupt_map = {"assistant": {"write_file": True}}
    bd.create_base_deepagent()
    assert patched.call_args.kwargs["interrupt_on"] == {"write_file": True}


def test_permissions_forwarded(patched, fake_meta):
    rules = [{"tool": "write_file", "path": "/workspace/**", "permission": "allow"}]
    fake_meta.permissions_map = {"assistant": rules}
    bd.create_base_deepagent()
    assert patched.call_args.kwargs["permissions"] == rules


def test_empty_interrupt_and_permissions_forward_none(patched):
    bd.create_base_deepagent()
    kwargs = patched.call_args.kwargs
    assert kwargs["interrupt_on"] is None
    assert kwargs["permissions"] is None
