# ABOUTME: Unit tests for ${VAR} environment interpolation in roster config values.
# ABOUTME: Verifies expansion, recursion into dicts/lists, and fail-fast on undefined vars.

import pytest

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as cfg
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    interpolate_env,
    load_agents_config,
)
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import DynagentSettings


@pytest.fixture
def _reset():
    """Reset agent config cache before and after each test using this fixture."""
    _reset_agent_config()
    yield
    _reset_agent_config()


def test_plain_values_pass_through():
    assert interpolate_env("no vars here") == "no vars here"
    assert interpolate_env(42) == 42
    assert interpolate_env(None) is None
    assert interpolate_env(True) is True


def test_expands_env_var_in_string(monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", "/tmp/ws")  # noqa: S108
    assert interpolate_env("${WORKSPACE_ROOT}/files") == "/tmp/ws/files"  # noqa: S108


def test_recurses_into_dicts_and_lists(monkeypatch):
    monkeypatch.setenv("TOKEN", "abc123")
    value = {"headers": {"Authorization": "Bearer ${TOKEN}"}, "paths": ["${TOKEN}/x"]}
    assert interpolate_env(value) == {
        "headers": {"Authorization": "Bearer abc123"},
        "paths": ["abc123/x"],
    }


def test_undefined_var_fails_fast(monkeypatch):
    monkeypatch.delenv("NOPE_NOT_SET", raising=False)
    with pytest.raises(ValueError, match="NOPE_NOT_SET"):
        interpolate_env("${NOPE_NOT_SET}")


def test_load_agents_config_interpolates(tmp_path, monkeypatch, _reset):
    monkeypatch.setenv("MY_PROMPT", "assistant")
    (tmp_path / "deep-agents.yaml").write_text(
        "agents:\n  assistant:\n    prompt: ${MY_PROMPT}\n    is_default: true\n    tools: []\n"
    )
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    settings = DynagentSettings(agents_config_filename="deep-agents.yaml")
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)

    agents = load_agents_config()
    assert agents["assistant"].prompt == "assistant"
