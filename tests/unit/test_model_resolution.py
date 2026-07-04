# ABOUTME: Unit tests for model-profile / inline model-ref resolution and validation.
# ABOUTME: Covers profile lookup, provider:name parsing, bare names, and load-time failures.

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as cfg
import autobots_devtools_shared_lib.dynagent.llm.model_resolution as mr
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    load_agents_config,
)
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import DynagentSettings

PROFILES = {
    "main": {"provider": "anthropic", "name": "claude-sonnet-4-6"},
    "cheap-docs": {"provider": "anthropic", "name": "claude-haiku-4-5", "temperature": 0.3},
    "settings-model": {"temperature": 0.7},
}


def test_profile_name_resolves_through_lm():
    with patch.object(mr, "lm", return_value="LLM") as lm_mock:
        assert mr.resolve_model_ref("cheap-docs", PROFILES) == "LLM"
    lm_mock.assert_called_once_with(model="claude-haiku-4-5", provider="anthropic", temperature=0.3)


def test_profile_with_omitted_fields_falls_back_to_settings():
    with patch.object(mr, "lm", return_value="LLM") as lm_mock:
        mr.resolve_model_ref("settings-model", PROFILES)
    lm_mock.assert_called_once_with(model=None, provider=None, temperature=0.7)


def test_inline_provider_model_string():
    with patch.object(mr, "lm", return_value="LLM") as lm_mock:
        mr.resolve_model_ref("anthropic:claude-opus-4-8", PROFILES)
    lm_mock.assert_called_once_with(model="claude-opus-4-8", provider="anthropic", temperature=None)


def test_bare_model_name_uses_settings_provider():
    with patch.object(mr, "lm", return_value="LLM") as lm_mock:
        mr.resolve_model_ref("claude-haiku-4-5", PROFILES)
    lm_mock.assert_called_once_with(model="claude-haiku-4-5", provider=None, temperature=None)


def test_none_ref_returns_plain_lm():
    with patch.object(mr, "lm", return_value="DEFAULT") as lm_mock:
        assert mr.resolve_model_ref(None, PROFILES) == "DEFAULT"
    lm_mock.assert_called_once_with()


def test_resolve_agent_model_reads_meta_maps():
    meta = SimpleNamespace(model_map={"researcher": "main"}, model_profiles=PROFILES)
    with patch.object(mr, "lm", return_value="LLM") as lm_mock:
        assert mr.resolve_agent_model(meta, "researcher") == "LLM"
    lm_mock.assert_called_once_with(
        model="claude-sonnet-4-6", provider="anthropic", temperature=None
    )


def test_validate_model_ref_rejects_unknown_inline_provider():
    with pytest.raises(ValueError, match="openai"):
        mr.validate_model_ref("openai:gpt-5.5", PROFILES)


def test_validate_model_profiles_rejects_unknown_provider():
    with pytest.raises(ValueError, match="bogus"):
        mr.validate_model_profiles({"bad": {"provider": "bogus", "name": "x"}})


def test_load_agents_config_fails_fast_on_bad_model_ref(tmp_path, monkeypatch):
    _reset_agent_config()
    (tmp_path / "deep-agents.yaml").write_text(
        "agents:\n"
        "  assistant:\n"
        "    prompt: assistant\n"
        "    is_default: true\n"
        "    model: openai:gpt-5.5\n"
        "    tools: []\n"
    )
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    settings = DynagentSettings(agents_config_filename="deep-agents.yaml")
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)

    with pytest.raises(ValueError, match="openai"):
        load_agents_config()
    _reset_agent_config()
