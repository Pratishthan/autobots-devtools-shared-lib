# ABOUTME: Pydantic settings for dynagent configuration.
# ABOUTME: Loads LLM, workspace, and observability settings from environment variables.
# ABOUTME: Use cases can extend DynagentSettings and register their instance via set_dynagent_settings().

from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    GEMINI = "gemini"
    ANTHROPIC = "anthropic"


class DynagentSettings(BaseSettings):
    """Base dynagent settings loaded from environment variables.

    Use cases (e.g. Jarvis) should subclass this, add their own fields, and call
    set_dynagent_settings(get_dynagent_settings()) at startup so shared-lib code uses the same instance.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM settings (env: LLM_PROVIDER, LLM_MODEL, LLM_TEMPERATURE, GOOGLE_API_KEY, ANTHROPIC_API_KEY)
    llm_provider: LLMProvider = Field(
        default=LLMProvider.GEMINI, description="LLM provider (gemini or anthropic)"
    )
    llm_model: str = Field(default="gemini-2.0-flash", description="LLM model name")
    llm_temperature: float = Field(default=0, description="LLM temperature")
    google_api_key: str = Field(
        default="", description="Google API key for Gemini (env: GOOGLE_API_KEY)"
    )
    anthropic_api_key: str = Field(
        default="", description="Anthropic API key for Claude (env: ANTHROPIC_API_KEY)"
    )

    # Workspace settings
    # TODO: Remove these settings
    workspace_base: Path = Field(default=Path("workspace"), description="Workspace base directory")
    schema_base: Path = Field(
        default=Path("schemas"), description="Base directory for JSON schemas"
    )
    dynagent_config_root_dir: Path = Field(
        default=Path("configs"),
        description="Base directory for agent configuration files",
    )

    # Langfuse observability settings
    langfuse_public_key: str = Field(default="", description="Langfuse public key")
    langfuse_secret_key: str = Field(default="", description="Langfuse secret key")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse host URL"
    )
    langfuse_enabled: bool = Field(default=True, description="Enable Langfuse tracing")

    def is_langfuse_configured(self) -> bool:
        """Check if Langfuse is properly configured."""
        return bool(self.langfuse_enabled and self.langfuse_public_key and self.langfuse_secret_key)


# Allow use cases to inject their extended settings so shared-lib uses one source of truth.
_settings: DynagentSettings | None = None


def set_dynagent_settings(instance: DynagentSettings) -> None:
    """Register the settings instance for use by shared-lib (e.g. after app startup)."""
    global _settings
    _settings = instance


def get_dynagent_settings() -> DynagentSettings:
    """Return the registered settings instance, or a default DynagentSettings()."""
    if _settings is not None:
        return _settings
    return DynagentSettings()


# Backward compatibility: Settings alias for DynagentSettings.
Settings = DynagentSettings
