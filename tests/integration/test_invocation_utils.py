# ABOUTME: Integration tests for invocation_utils against a live Gemini backend.
# ABOUTME: bro_registered_integration (autouse) in conftest handles tool registration.

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata
from autobots_devtools_shared_lib.dynagent.agents.invocation_utils import (
    ainvoke_agent,
    invoke_agent,
)
from tests.conftest import requires_google_api


@requires_google_api
def test_invoke_agent_basic():
    """Test basic sync invocation with real agent."""
    input_state = {"messages": [{"role": "user", "content": "Hello, what can you help with?"}]}
    config = {"configurable": {"thread_id": "test-invoke-basic"}}

    result = invoke_agent("coordinator", input_state, config)

    assert "messages" in result
    assert len(result["messages"]) > 1  # At least user message + AI response
    assert isinstance(result["messages"][0], HumanMessage)

    # Check that we have an AI response
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert len(ai_messages) > 0


@requires_google_api
def test_invoke_agent_with_tracing_disabled():
    """Test sync invocation with tracing disabled."""
    input_state = {"messages": [{"role": "user", "content": "Tell me about this system."}]}
    config = {"configurable": {"thread_id": "test-invoke-no-trace"}}

    result = invoke_agent("coordinator", input_state, config, enable_tracing=False)

    assert "messages" in result
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert len(ai_messages) > 0


@requires_google_api
def test_invoke_agent_with_custom_metadata():
    """Test sync invocation with custom TraceMetadata."""
    metadata = TraceMetadata(
        session_id="integration-test-session",
        app_name="test-invocation",
        user_id="test-user-123",
        tags=["integration", "test"],
    )

    input_state = {"messages": [{"role": "user", "content": "What agents are available?"}]}
    config = {"configurable": {"thread_id": "test-invoke-metadata"}}

    result = invoke_agent("coordinator", input_state, config, trace_metadata=metadata)

    assert "messages" in result
    assert "session_id" in result
    assert result["session_id"] == "integration-test-session"


@requires_google_api
def test_invoke_agent_preserves_session_id():
    """Test that session_id in input_state is preserved."""
    input_state = {
        "messages": [{"role": "user", "content": "Hello"}],
        "session_id": "my-custom-session-123",
    }
    config = {"configurable": {"thread_id": "test-invoke-session"}}

    result = invoke_agent("coordinator", input_state, config, enable_tracing=False)

    assert result["session_id"] == "my-custom-session-123"


@requires_google_api
def test_invoke_agent_different_agent():
    """Test invocation with different agent (preface_agent)."""
    input_state = {"messages": [{"role": "user", "content": "What is the preface section about?"}]}
    config = {"configurable": {"thread_id": "test-invoke-preface"}}

    result = invoke_agent("preface_agent", input_state, config, enable_tracing=False)

    assert "messages" in result
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert len(ai_messages) > 0


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


@requires_google_api
@pytest.mark.asyncio
async def test_ainvoke_agent_basic():
    """Test basic async invocation with real agent."""
    input_state = {"messages": [{"role": "user", "content": "Hello, what can you help with?"}]}
    config = {"configurable": {"thread_id": "test-ainvoke-basic"}}

    result = await ainvoke_agent("coordinator", input_state, config)

    assert "messages" in result
    assert len(result["messages"]) > 1
    assert isinstance(result["messages"][0], HumanMessage)

    # Check that we have an AI response
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert len(ai_messages) > 0


@requires_google_api
@pytest.mark.asyncio
async def test_ainvoke_agent_with_tracing_disabled():
    """Test async invocation with tracing disabled."""
    input_state = {"messages": [{"role": "user", "content": "Tell me about this system."}]}
    config = {"configurable": {"thread_id": "test-ainvoke-no-trace"}}

    result = await ainvoke_agent("coordinator", input_state, config, enable_tracing=False)

    assert "messages" in result
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert len(ai_messages) > 0


@requires_google_api
@pytest.mark.asyncio
async def test_ainvoke_agent_with_custom_metadata():
    """Test async invocation with custom TraceMetadata."""
    metadata = TraceMetadata(
        session_id="integration-test-session-async",
        app_name="test-invocation-async",
        user_id="test-user-456",
        tags=["integration", "async", "test"],
    )

    input_state = {"messages": [{"role": "user", "content": "What agents are available?"}]}
    config = {"configurable": {"thread_id": "test-ainvoke-metadata"}}

    result = await ainvoke_agent("coordinator", input_state, config, trace_metadata=metadata)

    assert "messages" in result
    assert "session_id" in result
    assert result["session_id"] == "integration-test-session-async"


@requires_google_api
@pytest.mark.asyncio
async def test_ainvoke_agent_preserves_session_id():
    """Test that session_id in input_state is preserved (async)."""
    input_state = {
        "messages": [{"role": "user", "content": "Hello"}],
        "session_id": "my-custom-session-async-456",
    }
    config = {"configurable": {"thread_id": "test-ainvoke-session"}}

    result = await ainvoke_agent("coordinator", input_state, config, enable_tracing=False)

    assert result["session_id"] == "my-custom-session-async-456"


@requires_google_api
@pytest.mark.asyncio
async def test_ainvoke_agent_different_agent():
    """Test async invocation with different agent (preface_agent)."""
    input_state = {"messages": [{"role": "user", "content": "What is the preface section about?"}]}
    config = {"configurable": {"thread_id": "test-ainvoke-preface"}}

    result = await ainvoke_agent("preface_agent", input_state, config, enable_tracing=False)

    assert "messages" in result
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert len(ai_messages) > 0


# ---------------------------------------------------------------------------
# Cross-version consistency tests
# ---------------------------------------------------------------------------


@requires_google_api
@pytest.mark.asyncio
async def test_sync_and_async_produce_similar_results():
    """Test that sync and async versions produce similar response structures."""
    input_state = {"messages": [{"role": "user", "content": "List the available agents."}]}
    config_sync = {"configurable": {"thread_id": "test-sync-result"}}
    config_async = {"configurable": {"thread_id": "test-async-result"}}

    # Run both versions
    sync_result = invoke_agent("coordinator", input_state.copy(), config_sync, enable_tracing=False)
    async_result = await ainvoke_agent(
        "coordinator", input_state.copy(), config_async, enable_tracing=False
    )

    # Both should have the same structure
    assert "messages" in sync_result
    assert "messages" in async_result
    assert len(sync_result["messages"]) > 1
    assert len(async_result["messages"]) > 1

    # Both should have AI responses
    sync_ai = [m for m in sync_result["messages"] if isinstance(m, AIMessage)]
    async_ai = [m for m in async_result["messages"] if isinstance(m, AIMessage)]
    assert len(sync_ai) > 0
    assert len(async_ai) > 0
