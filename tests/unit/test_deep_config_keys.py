# ABOUTME: Unit tests for deep-engine keys in deep-agents.yaml.
# ABOUTME: Covers per-agent model/skills/memory/etc. and top-level models/default_backend/mcp_servers.

import pytest

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as cfg
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    get_default_backend_config,
    get_mcp_servers_config,
    get_model_profiles,
    load_agents_config,
)
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import DynagentSettings

DEEP_YAML = """
models:
  main:
    provider: anthropic
    name: claude-sonnet-4-6
  cheap-docs:
    provider: anthropic
    name: claude-haiku-4-5
    temperature: 0.3

default_backend:
  type: filesystem
  root_dir: /tmp/ws

mcp_servers:
  atlassian:
    transport: streamable_http
    url: http://mcp.local

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
    permissions: []
    mcp_servers: ["atlassian"]
    debug: true
    rubric:
      model: cheap-docs
      max_iterations: 3
  researcher:
    prompt: researcher
    description: Deep research on a topic
    model: cheap-docs
    tools: []
"""


@pytest.fixture(autouse=True)
def deep_config(tmp_path, monkeypatch):
    _reset_agent_config()
    (tmp_path / "deep-agents.yaml").write_text(DEEP_YAML)
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    settings = DynagentSettings(agents_config_filename="deep-agents.yaml")
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)
    yield
    _reset_agent_config()


def test_per_agent_deep_fields_parsed():
    agents = load_agents_config()
    a = agents["assistant"]
    assert a.model == "main"
    assert a.skills == ["skills/"]
    assert a.memory == ["AGENTS.md"]
    assert a.interrupt_on == {"write_file": True}
    assert a.permissions == []
    assert a.mcp_servers == ["atlassian"]
    assert a.debug is True
    assert a.rubric == {"model": "cheap-docs", "max_iterations": 3}
    assert a.description is None


def test_subagent_entry_fields_parsed():
    agents = load_agents_config()
    r = agents["researcher"]
    assert r.description == "Deep research on a topic"
    assert r.model == "cheap-docs"
    assert r.is_default is False


def test_top_level_model_profiles():
    profiles = get_model_profiles()
    assert profiles["main"] == {"provider": "anthropic", "name": "claude-sonnet-4-6"}
    assert profiles["cheap-docs"]["temperature"] == 0.3


def test_top_level_default_backend():
    assert get_default_backend_config() == {"type": "filesystem", "root_dir": "/tmp/ws"}


def test_top_level_mcp_servers():
    servers = get_mcp_servers_config()
    assert servers["atlassian"]["transport"] == "streamable_http"


def test_blocks_default_to_empty(tmp_path, monkeypatch):
    _reset_agent_config()
    (tmp_path / "plain.yaml").write_text(
        "agents:\n  a:\n    prompt: a\n    is_default: true\n    tools: []\n"
    )
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    settings = DynagentSettings(agents_config_filename="plain.yaml")
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)

    agents = load_agents_config()
    assert get_model_profiles() == {}
    assert get_default_backend_config() is None
    assert get_mcp_servers_config() == {}
    assert agents["a"].model is None
    assert agents["a"].skills == []
    assert agents["a"].debug is False
