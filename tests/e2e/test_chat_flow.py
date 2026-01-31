# ABOUTME: End-to-end tests for chat flow functionality.
# ABOUTME: Tests the complete chat experience from message to response.

import pytest

from bro_chat.agents.crew import create_crew, run_chat
from bro_chat.config.settings import Settings
from bro_chat.observability.tracing import (
    flush_tracing,
    get_langfuse_client,
    get_langfuse_handler,
    init_tracing,
)
from tests.conftest import requires_openai


class TestTracingInitialization:
    """Tests for tracing initialization."""

    def test_init_tracing_returns_false_when_not_configured(
        self, test_settings: Settings
    ) -> None:
        """init_tracing should return False when Langfuse is not configured."""
        result = init_tracing(test_settings)
        assert result is False

    def test_get_langfuse_handler_returns_none_when_not_initialized(
        self, test_settings: Settings
    ) -> None:
        """get_langfuse_handler should return None when not initialized."""
        init_tracing(test_settings)
        handler = get_langfuse_handler()
        assert handler is None

    def test_get_langfuse_client_returns_none_when_not_initialized(
        self, test_settings: Settings
    ) -> None:
        """get_langfuse_client should return None when not initialized."""
        init_tracing(test_settings)
        client = get_langfuse_client()
        assert client is None

    def test_flush_tracing_does_not_error_when_not_initialized(
        self, test_settings: Settings
    ) -> None:
        """flush_tracing should not error when Langfuse is not initialized."""
        init_tracing(test_settings)
        flush_tracing()


class TestChatFlow:
    """Tests for the chat flow (requires OpenAI API key)."""

    @requires_openai
    def test_crew_can_be_created(self, test_settings: Settings) -> None:
        """A crew can be created with test settings."""
        crew = create_crew(test_settings)
        assert crew is not None
        assert len(crew.agents) > 0

    @requires_openai
    @pytest.mark.asyncio
    async def test_run_chat_with_simple_message(self, test_settings: Settings) -> None:
        """
        run_chat should process a message and return a response.

        Note: This test requires a valid OpenAI API key to execute.
        """
        crew = create_crew(test_settings)
        response = await run_chat(crew, "What is 2 + 2?")
        assert isinstance(response, str)
        assert len(response) > 0
