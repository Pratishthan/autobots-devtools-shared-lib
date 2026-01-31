# ABOUTME: Unit tests for settings configuration.
# ABOUTME: Tests Pydantic settings loading and validation.

import os

from bro_chat.config.settings import Settings, get_settings


class TestSettings:
    """Tests for the Settings class."""

    def test_default_values(self, clean_env: None) -> None:
        """Settings should have sensible defaults when env vars are not set."""
        settings = Settings()

        assert settings.openai_api_key == ""
        assert settings.langfuse_enabled is True
        assert settings.langfuse_host == "https://cloud.langfuse.com"
        assert settings.port == 1337
        assert settings.debug is False

    def test_loads_from_environment(self, clean_env: None) -> None:
        """Settings should load values from environment variables."""
        os.environ["OPENAI_API_KEY"] = "sk-test-key"
        os.environ["PORT"] = "8080"
        os.environ["DEBUG"] = "true"

        settings = Settings()

        assert settings.openai_api_key == "sk-test-key"
        assert settings.port == 8080
        assert settings.debug is True

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

    def test_oauth_configured_when_all_present(self) -> None:
        """is_oauth_configured should return True when all OAuth settings are set."""
        settings = Settings(
            oauth_github_client_id="client-id",
            oauth_github_client_secret="client-secret",
            chainlit_auth_secret="auth-secret",
        )

        assert settings.is_oauth_configured() is True

    def test_oauth_not_configured_when_missing(self) -> None:
        """is_oauth_configured should return False when OAuth settings are missing."""
        settings = Settings(
            oauth_github_client_id="client-id",
            oauth_github_client_secret="",
            chainlit_auth_secret="",
        )

        assert settings.is_oauth_configured() is False


class TestGetSettings:
    """Tests for the get_settings function."""

    def test_returns_settings_instance(self, clean_env: None) -> None:
        """get_settings should return a Settings instance."""
        settings = get_settings()

        assert isinstance(settings, Settings)

    def test_settings_use_defaults(self, clean_env: None) -> None:
        """get_settings should return settings with default values."""
        settings = get_settings()

        assert settings.port == 1337
