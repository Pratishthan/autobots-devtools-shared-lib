# ABOUTME: Pydantic settings for dynagent observability.
# ABOUTME: Extracts Langfuse fields so dynagent reads tracing config from env directly.

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Dynagent settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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
        return bool(
            self.langfuse_enabled
            and self.langfuse_public_key
            and self.langfuse_secret_key
        )


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
