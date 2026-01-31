# ABOUTME: Pydantic settings for bro-chat configuration.
# ABOUTME: Loads environment variables for API keys, Langfuse, and OAuth settings.

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google API key for CrewAI agents (Gemini)
    google_api_key: str = Field(default="", description="Google API key for Gemini")

    # Langfuse observability settings
    langfuse_public_key: str = Field(default="", description="Langfuse public key")
    langfuse_secret_key: str = Field(default="", description="Langfuse secret key")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse host URL"
    )
    langfuse_enabled: bool = Field(default=True, description="Enable Langfuse tracing")

    # GitHub OAuth settings for Chainlit
    oauth_github_client_id: str = Field(
        default="", description="GitHub OAuth client ID"
    )
    oauth_github_client_secret: str = Field(
        default="", description="GitHub OAuth client secret"
    )
    chainlit_auth_secret: str = Field(default="", description="Chainlit auth secret")

    # Application settings
    port: int = Field(default=1337, description="Application port")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Model configuration
    llm_model: str = Field(
        default="gemini/gemini-2.5-flash-lite",
        description="LLM model for CrewAI agents",
    )

    def is_langfuse_configured(self) -> bool:
        """Check if Langfuse is properly configured."""
        return bool(
            self.langfuse_enabled
            and self.langfuse_public_key
            and self.langfuse_secret_key
        )

    def is_oauth_configured(self) -> bool:
        """Check if GitHub OAuth is properly configured."""
        return bool(
            self.oauth_github_client_id
            and self.oauth_github_client_secret
            and self.chainlit_auth_secret
        )


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
