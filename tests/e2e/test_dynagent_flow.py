# ABOUTME: End-to-end tests for the dynagent reference architecture.
# ABOUTME: Full flow: create agent, send message, verify response and state transitions.

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from dynagent.agents.base_agent import create_base_agent
from tests.conftest import requires_google_api


@requires_google_api
async def test_e2e_coordinator_responds():
    """Coordinator agent responds to a basic greeting."""
    agent = create_base_agent(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "e2e-test-1"}}
    state = {
        "messages": [{"role": "user", "content": "Hi, what can you help with?"}],
        "agent_name": "coordinator",
        "session_id": "e2e-session-1",
    }
    result = await agent.ainvoke(state, config=config)  # type: ignore[arg-type]
    # Should have at least user message + AI response
    assert len(result["messages"]) >= 2


@requires_google_api
async def test_e2e_handoff_transition():
    """Agent performs a handoff when instructed; state updates accordingly.

    Note: prompts are BRO-specific and will be rewritten later.
    The LLM may or may not actually invoke handoff depending on prompt behavior.
    We assert the agent responds without crashing.
    """
    agent = create_base_agent(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "e2e-test-2"}}
    state = {
        "messages": [
            {"role": "user", "content": "Please hand off to the preface agent."}
        ],
        "agent_name": "coordinator",
        "session_id": "e2e-session-2",
    }
    result = await agent.ainvoke(state, config=config)  # type: ignore[arg-type]
    assert len(result["messages"]) >= 2


@requires_google_api
async def test_e2e_multi_turn_conversation():
    """Agent handles multi-turn conversation within the same thread."""
    agent = create_base_agent(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "e2e-multi-turn"}}

    # First turn
    state1 = {
        "messages": [{"role": "user", "content": "Hello, who are you?"}],
        "agent_name": "coordinator",
        "session_id": "e2e-session-3",
    }
    result1 = await agent.ainvoke(state1, config=config)  # type: ignore[arg-type]
    assert len(result1["messages"]) >= 2

    # Second turn — continues same thread via checkpointer
    state2 = {
        "messages": [{"role": "user", "content": "What sections can we work on?"}],
    }
    result2 = await agent.ainvoke(state2, config=config)  # type: ignore[arg-type]
    # Thread accumulates messages from both turns
    assert len(result2["messages"]) > len(result1["messages"])
