# ABOUTME: Pydantic settings for dynagent configuration.
# ABOUTME: Loads LLM, workspace, and observability settings from environment variables.

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Dynagent settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM settings
    llm_model: str = Field(default="gemini-2.0-flash", description="LLM model name")
    llm_temperature: float = Field(default=0, description="LLM temperature")

    # Workspace settings
    # TODO: Remove these settings
    workspace_base: Path = Field(default=Path("workspace"), description="Workspace base directory")

    dynagent_config_root_dir: Path = Field(
        default=Path("configs"),
        description="Base directory for agent configuration files",
    )
    schema_base: Path = Field(
        default=Path("schemas"),
        description="Base directory for JSON schemas (defaults to config_dir/schemas if not set)",
    )

    @model_validator(mode="after")
    def _schema_base_under_config_root(self) -> "Settings":
        # If schema_base is still the default "schemas", resolve under config root
        if self.schema_base == Path("schemas"):
            object.__setattr__(self, "schema_base", self.dynagent_config_root_dir / "schemas")
        return self

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


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
