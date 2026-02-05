# ABOUTME: Integration tests for the dynagent base agent creation.
# ABOUTME: Verifies create_base_agent produces a runnable agent with invoke capability.

from tests.conftest import requires_google_api


@requires_google_api
def test_create_base_agent_returns_agent():
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
        create_base_agent,
    )

    agent = create_base_agent()
    assert agent is not None


@requires_google_api
def test_create_base_agent_has_invoke():
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
        create_base_agent,
    )

    agent = create_base_agent()
    assert hasattr(agent, "invoke")
    assert hasattr(agent, "ainvoke")


@requires_google_api
async def test_create_base_agent_responds_to_message():
    from langchain_core.runnables import RunnableConfig
    from langgraph.checkpoint.memory import InMemorySaver

    from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
        create_base_agent,
    )

    agent = create_base_agent(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "base-agent-test-1"}}
    state = {
        "messages": [{"role": "user", "content": "Hello"}],
        "agent_name": "coordinator",
        "session_id": "integration-test-1",
    }
    result = await agent.ainvoke(state, config=config)  # type: ignore[arg-type]
    # Should have at least the user message + an AI response
    assert len(result["messages"]) >= 2
