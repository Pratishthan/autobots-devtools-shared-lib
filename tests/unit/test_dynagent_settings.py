# ABOUTME: Unit tests for dynagent settings configuration.
# ABOUTME: Tests Pydantic settings loading and validation.

import os

from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
    Settings,
    get_dynagent_settings,
)


class TestDynagentSettings:
    """Tests for the DynagentSettings (Settings) class."""

    def test_default_values(self, clean_env: None) -> None:
        """Settings should have sensible defaults when env vars are not set."""
        settings = Settings(_env_file=None)  # type: ignore[call-arg]

        assert settings.langfuse_enabled is True
        assert settings.langfuse_host == "https://cloud.langfuse.com"

    def test_loads_from_environment(self, clean_env: None) -> None:
        """Settings should load values from environment variables."""
        os.environ["LLM_MODEL"] = "gemini-2.0-flash"

        settings = Settings()

        assert settings.llm_model == "gemini-2.0-flash"

    def test_langfuse_configured_when_keys_present(self) -> None:
        """is_langfuse_configured should return True when all keys are set."""
        settings = Settings(
            langfuse_enabled=True,
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
        )

        assert settings.is_langfuse_configured() is True

    def test_langfuse_not_configured_when_disabled(self) -> None:
        """is_langfuse_configured should return False when disabled."""
        settings = Settings(
            langfuse_enabled=False,
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
        )

        assert settings.is_langfuse_configured() is False

    def test_langfuse_not_configured_when_keys_missing(self) -> None:
        """is_langfuse_configured should return False when keys are missing."""
        settings = Settings(
            langfuse_enabled=True,
            langfuse_public_key="",
            langfuse_secret_key="",
        )

        assert settings.is_langfuse_configured() is False

    def test_llm_api_keys_default_empty(self, clean_env: None) -> None:
        """LLM API key fields should default to empty string when env vars are unset."""
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.google_api_key == ""
        assert settings.anthropic_api_key == ""


class TestGetDynagentSettings:
    """Tests for the get_dynagent_settings function."""

    def test_returns_settings_instance(self, clean_env: None) -> None:
        """get_dynagent_settings should return a Settings instance."""
        settings = get_dynagent_settings()

        assert isinstance(settings, Settings)

    def test_settings_use_defaults(self, clean_env: None) -> None:
        """get_dynagent_settings should return settings with default values."""
        settings = get_dynagent_settings()

        assert settings.langfuse_enabled is True
        assert settings.langfuse_host == "https://cloud.langfuse.com"
