# ABOUTME: Unit tests for AgentMeta's deep-engine maps.
# ABOUTME: Verifies model/skills/memory/interrupt/permissions/description/mcp/debug/rubric maps.

import pytest

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as cfg
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import _reset_agent_config
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import DynagentSettings

DEEP_YAML = """
models:
  main:
    provider: anthropic
    name: claude-sonnet-4-6

default_backend:
  type: state

agents:
  assistant:
    prompt: assistant
    is_default: true
    model: main
    tools: []
    skills: ["skills/"]
    memory: ["AGENTS.md"]
    interrupt_on:
      write_file: true
    debug: true
  researcher:
    prompt: researcher
    description: Deep research on a topic
    tools: []
    rubric:
      max_iterations: 2
"""


@pytest.fixture(autouse=True)
def deep_config(tmp_path, monkeypatch):
    _reset_agent_config()
    AgentMeta.reset()
    (tmp_path / "deep-agents.yaml").write_text(DEEP_YAML)
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "assistant.md").write_text("You are an assistant.")
    (tmp_path / "prompts" / "researcher.md").write_text("You are a researcher.")
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    settings = DynagentSettings(agents_config_filename="deep-agents.yaml")
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)
    yield
    _reset_agent_config()
    AgentMeta.reset()


def test_meta_exposes_deep_maps():
    meta = AgentMeta.instance()
    assert meta.model_map == {"assistant": "main", "researcher": None}
    assert meta.skills_map == {"assistant": ["skills/"], "researcher": []}
    assert meta.memory_map == {"assistant": ["AGENTS.md"], "researcher": []}
    assert meta.interrupt_map == {"assistant": {"write_file": True}, "researcher": {}}
    assert meta.permissions_map == {"assistant": [], "researcher": []}
    assert meta.description_map == {"assistant": None, "researcher": "Deep research on a topic"}
    assert meta.mcp_map == {"assistant": [], "researcher": []}
    assert meta.debug_map == {"assistant": True, "researcher": False}
    assert meta.rubric_map == {"assistant": None, "researcher": {"max_iterations": 2}}


def test_meta_exposes_domain_level_blocks():
    meta = AgentMeta.instance()
    assert meta.backend_config == {"type": "state"}
    assert meta.model_profiles == {"main": {"provider": "anthropic", "name": "claude-sonnet-4-6"}}
    assert meta.mcp_servers_config == {}
