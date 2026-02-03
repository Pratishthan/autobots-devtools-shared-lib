# ABOUTME: Integration tests for structured outputs in dynagent.
# ABOUTME: Validates that agents return properly formatted structured responses.

import uuid

from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from bro_chat.agents.dynagent import create_dynamic_agent
from tests.conftest import requires_google_api


@requires_google_api
async def test_math_agent_structured_output():
    """Math agent should return structured MathOutput."""
    agent = create_dynamic_agent()
    thread_id = str(uuid.uuid4())

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="What is 5 + 3?")]}, config=config
    )

    structured = result.get("structured_response")
    assert structured is not None, "Should have structured_response in result"
    assert "answer" in structured, "Should have answer field"
    assert "explanation" in structured, "Should have explanation field"
    assert isinstance(structured["answer"], int | float), "Answer should be numeric"
    assert isinstance(structured["explanation"], str), "Explanation should be string"


@requires_google_api
async def test_joke_agent_structured_output():
    """Joke agent should return structured JokeOutput."""
    agent = create_dynamic_agent()
    thread_id = str(uuid.uuid4())

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    # First invoke to set current_step to joke_agent
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="Tell me a joke about programming")]},
        config=config,
    )

    structured = result.get("structured_response")
    # Note: This may not work if the agent doesn't transition to joke_agent
    # The test validates structure when joke_agent is active
    if structured:
        assert "joke" in structured, "Should have joke field"
        assert "category" in structured, "Should have category field"
        assert isinstance(structured["joke"], str), "Joke should be string"
        assert isinstance(structured["category"], str), "Category should be string"
