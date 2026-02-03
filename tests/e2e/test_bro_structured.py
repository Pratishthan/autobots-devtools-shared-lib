# ABOUTME: E2E tests for bro agents with structured outputs.
# ABOUTME: Validates full agent flow returns properly formatted structured responses.

import uuid
from pathlib import Path

from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from bro_chat.agents.bro.factory import create_bro_agent
from bro_chat.services.document_store import DocumentStore
from tests.conftest import requires_google_api


@requires_google_api
async def test_preface_agent_structured_output(tmp_path: Path):
    """Preface agent should return structured PrefaceOutput."""
    store = DocumentStore(base_path=tmp_path)

    # Create a test document
    store.create_document(component="payment-service", version="v1")

    agent = create_bro_agent(store=store)
    thread_id = str(uuid.uuid4())

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    result = await agent.ainvoke(
        {  # type: ignore[arg-type]
            "messages": [
                HumanMessage(
                    content="Create preface section for payment service component"
                )
            ],
            "component": "payment-service",
            "version": "v1",
            "current_step": "preface_agent",
        },
        config=config,
    )

    structured = result.get("structured_response")
    assert structured is not None, "Should have structured_response"
    assert "about_this_guide" in structured, "Should have about_this_guide field"
    assert "audience" in structured, "Should have audience field"
    assert isinstance(structured["audience"], list), "Audience should be a list"
    assert len(structured["audience"]) >= 1, "Should have at least one audience member"


@requires_google_api
async def test_features_agent_structured_output(tmp_path: Path):
    """Features agent should return structured FeaturesOutput."""
    store = DocumentStore(base_path=tmp_path)

    # Create a test document
    store.create_document(component="auth-service", version="v1")

    agent = create_bro_agent(store=store)
    thread_id = str(uuid.uuid4())

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    result = await agent.ainvoke(
        {  # type: ignore[arg-type]
            "messages": [
                HumanMessage(
                    content="Create a list of features for an authentication service"
                )
            ],
            "component": "auth-service",
            "version": "v1",
            "current_step": "features_agent",
        },
        config=config,
    )

    structured = result.get("structured_response")
    assert structured is not None, "Should have structured_response"
    assert "features" in structured, "Should have features field"
    assert isinstance(structured["features"], list), "Features should be a list"

    if len(structured["features"]) > 0:
        feature = structured["features"][0]
        assert "name" in feature, "Feature should have name"
        assert "description" in feature, "Feature should have description"
        assert "category" in feature, "Feature should have category"
        assert "priority" in feature, "Feature should have priority"


@requires_google_api
async def test_entity_agent_structured_output(tmp_path: Path):
    """Entity agent should return structured EntityOutput."""
    store = DocumentStore(base_path=tmp_path)

    # Create a test document
    store.create_document(component="user-service", version="v1")

    agent = create_bro_agent(store=store)
    thread_id = str(uuid.uuid4())

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }

    result = await agent.ainvoke(
        {  # type: ignore[arg-type]
            "messages": [
                HumanMessage(content="Define a User entity with basic fields")
            ],
            "component": "user-service",
            "version": "v1",
            "current_step": "entity_agent",
            "entity_name": "User",
        },
        config=config,
    )

    structured = result.get("structured_response")
    assert structured is not None, "Should have structured_response"
    assert "name" in structured, "Should have name field"
    assert "description" in structured, "Should have description field"
    assert "attributes" in structured, "Should have attributes field"
    assert isinstance(structured["attributes"], list), "Attributes should be a list"
    assert len(structured["attributes"]) >= 1, "Should have at least one attribute"

    if len(structured["attributes"]) > 0:
        attr = structured["attributes"][0]
        assert "name" in attr, "Attribute should have name"
        assert "type" in attr, "Attribute should have type"
