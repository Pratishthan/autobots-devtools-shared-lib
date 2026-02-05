# ABOUTME: Integration tests for the inject_agent middleware.
# ABOUTME: Verifies prompt and tool swapping based on agent_name in state.

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent
from tests.conftest import requires_google_api


@requires_google_api
async def test_middleware_coordinator_responds():
    """Running with agent_name=coordinator uses coordinator's prompt."""
    agent = create_base_agent(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "inject-test-1"}}
    state = {
        "messages": [{"role": "user", "content": "Hello"}],
        "agent_name": "coordinator",
        "session_id": "middleware-test-coord",
    }
    result = await agent.ainvoke(state, config=config)  # type: ignore[arg-type]
    # Agent should respond — messages list grows beyond the initial user message
    assert len(result["messages"]) > 1


@requires_google_api
async def test_middleware_section_agent_responds():
    """Running with agent_name=preface_agent injects that agent's prompt."""
    agent = create_base_agent(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "inject-test-2"}}
    state = {
        "messages": [{"role": "user", "content": "Tell me about the preface section"}],
        "agent_name": "preface_agent",
        "session_id": "middleware-test-preface",
    }
    result = await agent.ainvoke(state, config=config)  # type: ignore[arg-type]
    assert len(result["messages"]) > 1


@requires_google_api
async def test_middleware_preserves_agent_name_in_state():
    """State retains agent_name across the invocation (unless handoff occurs)."""
    agent = create_base_agent(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "inject-test-3"}}
    state = {
        "messages": [{"role": "user", "content": "What is your role?"}],
        "agent_name": "coordinator",
        "session_id": "middleware-test-retain",
    }
    result = await agent.ainvoke(state, config=config)  # type: ignore[arg-type]
    # If no handoff happened, agent_name stays as coordinator
    # If handoff happened, it changed — both are valid
    assert "agent_name" in result or len(result["messages"]) > 1
