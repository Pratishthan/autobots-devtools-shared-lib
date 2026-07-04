# ABOUTME: Unit tests for config-driven subagent mapping in the deep engine.
# ABOUTME: Covers roster->SubAgent fields, model inheritance, kwarg merge, description validation.

from unittest.mock import MagicMock, patch

import pytest

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as cfg
import autobots_devtools_shared_lib.dynagent.agents.base_deepagent as bd
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    load_agents_config,
)
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import DynagentSettings


@pytest.fixture
def fake_meta():
    meta = MagicMock()
    meta.prompt_map = {
        "assistant": "You are an assistant.",
        "researcher": "You research {language}.",
    }
    meta.tool_map = {"assistant": ["tool_a"], "researcher": ["tool_r"]}
    meta.input_schema_map = {"assistant": {}, "researcher": {}}
    meta.output_schema_map = {"assistant": None, "researcher": None}
    meta.model_map = {"assistant": None, "researcher": None}
    meta.skills_map = {"assistant": [], "researcher": []}
    meta.memory_map = {"assistant": [], "researcher": []}
    meta.interrupt_map = {"assistant": {}, "researcher": {}}
    meta.permissions_map = {"assistant": [], "researcher": []}
    meta.description_map = {"assistant": None, "researcher": "Does research"}
    meta.mcp_map = {"assistant": [], "researcher": []}
    meta.debug_map = {"assistant": False, "researcher": False}
    meta.rubric_map = {"assistant": None, "researcher": None}
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


def _subagents(mock_cda):
    return mock_cda.call_args.kwargs["subagents"]


def test_non_default_roster_entry_becomes_subagent(patched):
    bd.create_base_deepagent(prompt_values={"language": "java"})
    subs = _subagents(patched)
    assert len(subs) == 1
    sub = subs[0]
    assert sub["name"] == "researcher"
    assert sub["description"] == "Does research"
    assert sub["system_prompt"] == "You research java."
    assert sub["tools"] == ["tool_r"]
    assert "model" not in sub  # inherits the main agent's model natively


def test_subagent_model_set_only_when_configured(patched, fake_meta):
    fake_meta.model_map = {"assistant": None, "researcher": "cheap-docs"}
    bd.create_base_deepagent()
    sub = _subagents(patched)[0]
    assert sub["model"] == "MODEL"


def test_subagent_skills_forwarded_when_present(patched, fake_meta):
    fake_meta.skills_map = {"assistant": [], "researcher": ["skills/research/"]}
    bd.create_base_deepagent()
    assert _subagents(patched)[0]["skills"] == ["skills/research/"]


def test_kwarg_subagents_are_additive(patched):
    extra = {"name": "extra", "description": "d", "system_prompt": "p"}
    bd.create_base_deepagent(subagents=[extra])
    names = {s["name"] for s in _subagents(patched)}
    assert names == {"researcher", "extra"}


def test_kwarg_wins_on_name_collision(patched):
    override = {"name": "researcher", "description": "override", "system_prompt": "p"}
    bd.create_base_deepagent(subagents=[override])
    subs = _subagents(patched)
    assert len(subs) == 1
    assert subs[0]["description"] == "override"


def test_no_subagents_forwards_none(patched, fake_meta):
    fake_meta.prompt_map = {"assistant": "You are an assistant."}
    fake_meta.tool_map = {"assistant": []}
    fake_meta.description_map = {"assistant": None}
    bd.create_base_deepagent()
    assert patched.call_args.kwargs["subagents"] is None


def test_missing_description_fails_at_config_load(tmp_path, monkeypatch):
    _reset_agent_config()
    (tmp_path / "deep-agents.yaml").write_text(
        "agents:\n"
        "  assistant:\n"
        "    prompt: assistant\n"
        "    is_default: true\n"
        "    tools: []\n"
        "  researcher:\n"
        "    prompt: researcher\n"
        "    tools: []\n"
    )
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    settings = DynagentSettings(agents_config_filename="deep-agents.yaml")
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)
    with pytest.raises(ValueError, match=r"researcher.*description"):
        load_agents_config()
    _reset_agent_config()


def test_react_roster_without_descriptions_still_loads(tmp_path, monkeypatch):
    _reset_agent_config()
    (tmp_path / "agents.yaml").write_text(
        "agents:\n"
        "  coordinator:\n"
        "    prompt: coordinator\n"
        "    is_default: true\n"
        "    tools: []\n"
        "  worker:\n"
        "    prompt: worker\n"
        "    tools: []\n"
    )
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    settings = DynagentSettings(agents_config_filename="agents.yaml")
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)
    agents = load_agents_config()
    assert set(agents) == {"coordinator", "worker"}
    _reset_agent_config()


def test_subagent_response_format_forwarded_when_present(patched, fake_meta):
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    fake_meta.output_schema_map = {"assistant": None, "researcher": schema}
    bd.create_base_deepagent()
    assert _subagents(patched)[0]["response_format"] == schema


def test_subagent_interrupt_on_forwarded_when_present(patched, fake_meta):
    interrupt_config = {"write_file": True}
    fake_meta.interrupt_map = {"assistant": {}, "researcher": interrupt_config}
    bd.create_base_deepagent()
    assert _subagents(patched)[0]["interrupt_on"] == interrupt_config


def test_subagent_permissions_forwarded_when_present(patched, fake_meta):
    permissions = ["read", "write"]
    fake_meta.permissions_map = {"assistant": [], "researcher": permissions}
    bd.create_base_deepagent()
    assert _subagents(patched)[0]["permissions"] == permissions


def test_subagent_omits_response_format_interrupt_permissions_when_unset(patched):
    bd.create_base_deepagent()
    sub = _subagents(patched)[0]
    assert "response_format" not in sub
    assert "interrupt_on" not in sub
    assert "permissions" not in sub


def test_rubric_enabled_subagent_gets_middleware(patched, fake_meta, monkeypatch):
    rubric_mw = object()
    fake_meta.rubric_map = {"assistant": None, "researcher": {"max_iterations": 2}}
    monkeypatch.setattr(
        bd,
        "build_rubric_middleware",
        lambda _meta, name, _model: rubric_mw if name == "researcher" else None,
    )
    bd.create_base_deepagent()
    sub = _subagents(patched)[0]
    assert sub["middleware"] == [rubric_mw]
