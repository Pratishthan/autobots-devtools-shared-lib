# ABOUTME: Pytest fixtures and configuration for bro-chat tests.
# ABOUTME: Provides shared fixtures for settings, crew, and test utilities.

import os
from collections.abc import Generator

import pytest

from bro_chat.config.settings import Settings


def has_real_google_key() -> bool:
    """Check if a real Google API key is available."""
    key = os.environ.get("GOOGLE_API_KEY", "")
    return len(key) > 20


requires_google_api = pytest.mark.skipif(
    not has_real_google_key(),
    reason="Requires real GOOGLE_API_KEY environment variable",
)


@pytest.fixture
def test_settings() -> Settings:
    """Create settings for testing with minimal configuration."""
    return Settings(
        google_api_key=os.environ.get("GOOGLE_API_KEY", "test-google-key"),
        langfuse_enabled=False,
        langfuse_public_key="",
        langfuse_secret_key="",
        oauth_github_client_id="",
        oauth_github_client_secret="",
        chainlit_auth_secret="",
        debug=True,
    )


@pytest.fixture
def langfuse_settings() -> Settings:
    """Create settings with Langfuse configuration."""
    return Settings(
        google_api_key=os.environ.get("GOOGLE_API_KEY", "test-google-key"),
        langfuse_enabled=True,
        langfuse_public_key="test-public-key",
        langfuse_secret_key="test-secret-key",
        langfuse_host="https://test.langfuse.com",
        debug=True,
    )


@pytest.fixture
def oauth_settings() -> Settings:
    """Create settings with OAuth configuration."""
    return Settings(
        google_api_key=os.environ.get("GOOGLE_API_KEY", "test-google-key"),
        langfuse_enabled=False,
        oauth_github_client_id="test-client-id",
        oauth_github_client_secret="test-client-secret",
        chainlit_auth_secret="test-auth-secret",
        debug=True,
    )


@pytest.fixture
def bro_registered():
    """Register BRO tools; reset after test."""
    from bro_chat.agents.bro_tools import register_bro_tools
    from dynagent.agents.agent_meta import AgentMeta
    from dynagent.tools.tool_registry import _reset_usecase_tools

    _reset_usecase_tools()
    AgentMeta.reset()
    register_bro_tools()
    yield
    _reset_usecase_tools()
    AgentMeta.reset()


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Temporarily clear environment variables for testing."""
    env_vars = [
        "GOOGLE_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "LANGFUSE_ENABLED",
        "OAUTH_GITHUB_CLIENT_ID",
        "OAUTH_GITHUB_CLIENT_SECRET",
        "CHAINLIT_AUTH_SECRET",
        "PORT",
        "DEBUG",
    ]

    old_values = {var: os.environ.get(var) for var in env_vars}

    for var in env_vars:
        os.environ.pop(var, None)

    yield

    for var, value in old_values.items():
        if value is not None:
            os.environ[var] = value
        else:
            os.environ.pop(var, None)
