# ABOUTME: Unit tests for lm() override arguments (model, provider, temperature).
# ABOUTME: Verifies settings-backed defaults, per-call overrides, and unknown-provider failure.

from unittest.mock import patch

import pytest

import autobots_devtools_shared_lib.dynagent.llm.llm as llm_mod
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
    DynagentSettings,
    LLMProvider,
)
from autobots_devtools_shared_lib.dynagent.llm.llm import lm


@pytest.fixture
def anthropic_settings(monkeypatch):
    settings = DynagentSettings(
        llm_provider=LLMProvider.ANTHROPIC,
        llm_model="claude-sonnet-4-6",
        llm_temperature=0.0,
        anthropic_api_key="test-key",
    )
    monkeypatch.setattr(llm_mod, "get_dynagent_settings", lambda: settings)
    return settings


def test_no_args_uses_settings(anthropic_settings):
    with patch.object(llm_mod, "_build_anthropic", return_value="LLM") as build:
        assert lm() == "LLM"
    build.assert_called_once_with("claude-sonnet-4-6", 0.0, "test-key")


def test_model_and_temperature_overrides(anthropic_settings):
    with patch.object(llm_mod, "_build_anthropic", return_value="LLM") as build:
        lm(model="claude-haiku-4-5", temperature=0.3)
    build.assert_called_once_with("claude-haiku-4-5", 0.3, "test-key")


def test_provider_override_routes_to_gemini(anthropic_settings, monkeypatch):
    with patch.object(llm_mod, "_build_gemini", return_value="GEM") as build:
        assert lm(model="gemini-2.0-flash", provider="gemini") == "GEM"
    build.assert_called_once_with("gemini-2.0-flash", 0.0, "")


def test_unknown_provider_raises(anthropic_settings):
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        lm(provider="openai")


def test_temperature_zero_is_respected(anthropic_settings):
    """0.0 must not be treated as falsy-missing."""
    with patch.object(llm_mod, "_build_anthropic", return_value="LLM") as build:
        lm(temperature=0.0)
    build.assert_called_once_with("claude-sonnet-4-6", 0.0, "test-key")
