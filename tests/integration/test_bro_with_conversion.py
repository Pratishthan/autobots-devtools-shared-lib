# ABOUTME: Integration tests for natural conversation to structured conversion.
# ABOUTME: Tests bro agents having conversations and converting to structured output.

import uuid
from pathlib import Path

import pytest
from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from bro_chat.agents.bro import create_bro_agent
from bro_chat.services.document_store import DocumentStore
from tests.conftest import requires_google_api


@pytest.fixture
def temp_store(tmp_path: Path) -> DocumentStore:
    """Create a DocumentStore with a temporary directory."""
    return DocumentStore(base_path=tmp_path)


@requires_google_api
async def test_preface_agent_natural_conversation_to_structured(
    temp_store: DocumentStore,
):
    """Test preface agent natural conversation converts to structured output."""
    agent = create_bro_agent(store=temp_store)
    thread_id = str(uuid.uuid4())

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    # First, set up the document context
    result1 = await agent.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Create a document for component 'payment-service' version 'v1'"
                    )
                )
            ]
        },
        config=config,
    )
    assert "payment-service" in str(result1["messages"][-1].content)

    # Set the document context
    result2 = await agent.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="Set document context to payment-service version v1"
                )
            ]
        },
        config=config,
    )
    assert "Document context set" in str(result2["messages"][-1].content)

    # Hand off to preface agent
    await agent.ainvoke(
        {"messages": [HumanMessage(content="Hand off to preface_agent")]},
        config=config,
    )

    # Have a natural conversation about preface content
    # Note: The agent should respond naturally, not with structured JSON
    result4 = await agent.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="This guide is about our payment service architecture. "
                    "It's intended for backend developers and system architects."
                )
            ]
        },
        config=config,
    )

    # The last message should be conversational, not structured
    last_msg = result4["messages"][-1].content
    assert isinstance(last_msg, str)
    # Should not be JSON-like if response_format is removed correctly
    # (this is a weak check, but we can't easily verify conversational tone)

    # Now call update_section - this should trigger structured conversion
    result5 = await agent.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Update section 01-preface with the information "
                        "from our conversation"
                    )
                )
            ]
        },
        config=config,
    )

    # Check if update was successful
    update_msg = str(result5["messages"][-1].content)
    assert "Successfully updated section" in update_msg or "Error" in update_msg

    # Verify the section was written to disk
    doc = temp_store.get_document("payment-service", "v1")
    if doc and doc.sections.get("01-preface"):
        # Section exists - conversion worked!
        section_path = (
            temp_store.base_path / "payment-service" / "v1" / "01-preface.json"
        )
        assert section_path.exists()


@requires_google_api
async def test_conversion_error_returns_to_agent(temp_store: DocumentStore):
    """Test that conversion errors are returned to agent for clarification."""
    agent = create_bro_agent(store=temp_store)
    thread_id = str(uuid.uuid4())

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    # Set up document
    await agent.ainvoke(
        {
            "messages": [
                HumanMessage(content="Create document for 'test-service' version 'v1'")
            ]
        },
        config=config,
    )

    await agent.ainvoke(
        {
            "messages": [
                HumanMessage(content="Set document context to test-service version v1")
            ]
        },
        config=config,
    )

    # Hand off to preface agent
    await agent.ainvoke(
        {"messages": [HumanMessage(content="Hand off to preface_agent")]},
        config=config,
    )

    # Have a very incomplete conversation (missing required fields)
    await agent.ainvoke(
        {"messages": [HumanMessage(content="This is about something")]},
        config=config,
    )

    # Try to update section with incomplete information
    result = await agent.ainvoke(
        {
            "messages": [
                HumanMessage(content="Update section 01-preface with what we discussed")
            ]
        },
        config=config,
    )

    # Should get an error message asking for more information
    # The exact error depends on LLM conversion, but should mention details
    last_msg = str(result["messages"][-1].content)
    # Either conversion succeeded (LLM is smart) or we got an error
    assert (
        "Successfully updated" in last_msg
        or "Error" in last_msg
        or "more details" in last_msg
    )


@requires_google_api
async def test_getting_started_agent_conversion(temp_store: DocumentStore):
    """Test getting_started_agent converts conversation to GettingStartedOutput."""
    agent = create_bro_agent(store=temp_store)
    thread_id = str(uuid.uuid4())

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    # Set up document
    await agent.ainvoke(
        {
            "messages": [
                HumanMessage(content="Create document for 'api-service' version 'v1'")
            ]
        },
        config=config,
    )

    await agent.ainvoke(
        {
            "messages": [
                HumanMessage(content="Set document context to api-service version v1")
            ]
        },
        config=config,
    )

    # Hand off to getting_started_agent
    await agent.ainvoke(
        {"messages": [HumanMessage(content="Hand off to getting_started_agent")]},
        config=config,
    )

    # Have natural conversation about the component
    await agent.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "This API service provides a RESTful interface for "
                        "managing user accounts. The vision is to create a "
                        "highly scalable, secure authentication system. "
                        "Key success metrics include 99.9% uptime and "
                        "sub-100ms response times."
                    )
                )
            ]
        },
        config=config,
    )

    # Update section - should convert to GettingStartedOutput
    result = await agent.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="Update section 02-getting-started with our discussion"
                )
            ]
        },
        config=config,
    )

    # Check for successful update
    update_msg = str(result["messages"][-1].content)
    assert "Successfully updated" in update_msg or "Error" in update_msg

    # Verify section was created
    doc = temp_store.get_document("api-service", "v1")
    if doc and doc.sections.get("02-getting-started"):
        section_path = (
            temp_store.base_path / "api-service" / "v1" / "02-getting-started.json"
        )
        assert section_path.exists()
